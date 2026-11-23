"""聚合口径描述：本地计算与多维查询共用的聚合口径、版本登记与存量恢复。

本地报告（MetricDef.compute）和多维查询（OlapQuery.build_sql）不再各自
维护聚合分支，而是通过 aggregation_spec_for 选取同一份 AggregationSpec：

- compute_local 负责离线指标计算，仍按本地行数据计数；
- sql_expression 负责生成多维查询的聚合表达式与别名，写法与原来一致。

SpecRegistry 登记指标口径版本：看板计划在登记时钉住口径版本，同一次看板
分析的本地统计与 SQL 识别同一版本；并发提交同一份看板只确认一次；历史报告
按原口径重算；无口径版本号的存量分析仅在指标身份与留存 SQL 的聚合方式都
唯一对上时才可恢复，歧义时当次分析停在待核。
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from app.models import AggregationMethod, MetricDef, OlapQuery, _percentile

# ============================================================
# 计划与执行状态
# ============================================================

PLAN_PENDING = "待执行"
PLAN_CONFIRMED = "已确认"
PLAN_CONFLICT = "口径冲突"
PLAN_REVIEW = "待核"
RUN_DONE = "已执行"


# ============================================================
# 共用聚合口径描述
# ============================================================

def _numeric_values(rows: list[dict[str, Any]], field_name: str) -> list[float]:
    """提取可转成数字的本地值；空值和无法转换的文本跳过。"""
    values: list[float] = []
    for row in rows:
        v = row.get(field_name)
        if v is not None:
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                pass
    return values


def _local_count(rows: list[dict[str, Any]], field_name: str) -> float:
    # 既定行为：本地 Count 按行数计数，不看字段取值。
    return float(len(rows))


def _local_count_distinct(rows: list[dict[str, Any]], field_name: str) -> float:
    raw = [row.get(field_name) for row in rows]
    return float(len({v for v in raw if v is not None}))


def _local_sum(rows: list[dict[str, Any]], field_name: str) -> float:
    values = _numeric_values(rows, field_name)
    return sum(values) if values else 0.0


def _local_avg(rows: list[dict[str, Any]], field_name: str) -> float:
    values = _numeric_values(rows, field_name)
    return sum(values) / len(values) if values else 0.0


def _local_max(rows: list[dict[str, Any]], field_name: str) -> float:
    values = _numeric_values(rows, field_name)
    return max(values) if values else 0.0


def _local_min(rows: list[dict[str, Any]], field_name: str) -> float:
    values = _numeric_values(rows, field_name)
    return min(values) if values else 0.0


def _local_percentile(percent: float) -> Callable[[list[dict[str, Any]], str], float]:
    def impl(rows: list[dict[str, Any]], field_name: str) -> float:
        values = _numeric_values(rows, field_name)
        return _percentile(values, percent) if values else 0.0
    return impl


# 本地计算实现表：离线指标计算按本地值计数。
_LOCAL_AGGREGATIONS: dict[AggregationMethod, Callable[[list[dict[str, Any]], str], float]] = {
    AggregationMethod.COUNT: _local_count,
    AggregationMethod.COUNT_DISTINCT: _local_count_distinct,
    AggregationMethod.SUM: _local_sum,
    AggregationMethod.AVG: _local_avg,
    AggregationMethod.MAX: _local_max,
    AggregationMethod.MIN: _local_min,
    AggregationMethod.P50: _local_percentile(50),
    AggregationMethod.P90: _local_percentile(90),
    AggregationMethod.P99: _local_percentile(99),
}

# SQL 聚合表达式模板：多维查询入口沿用原来的写法。
_SQL_TEMPLATES: dict[AggregationMethod, str] = {
    AggregationMethod.COUNT_DISTINCT: "COUNT(DISTINCT {field})",
    AggregationMethod.SUM: "SUM({field})",
    AggregationMethod.AVG: "AVG({field})",
    AggregationMethod.COUNT: "COUNT({field})",
    AggregationMethod.MAX: "MAX({field})",
    AggregationMethod.MIN: "MIN({field})",
    AggregationMethod.P50: "PERCENTILE({field}, 0.5)",
    AggregationMethod.P90: "PERCENTILE({field}, 0.9)",
    AggregationMethod.P99: "PERCENTILE({field}, 0.99)",
}


@dataclass(frozen=True)
class AggregationSpec:
    """聚合口径描述：一种聚合方式在某个字段和别名下的完整口径。"""
    method: AggregationMethod
    field_name: str
    alias: str

    def compute_local(self, rows: list[dict[str, Any]]) -> float:
        """离线指标计算：按本地行数据确定性计算。"""
        impl = _LOCAL_AGGREGATIONS.get(self.method)
        if impl is None:
            return 0.0
        return impl(rows, self.field_name)

    def sql_expression(self) -> str:
        """多维查询拼接：生成聚合表达式与别名。"""
        template = _SQL_TEMPLATES[self.method]
        return f"{template.format(field=self.field_name)} AS {self.alias}"

    def signature(self) -> str:
        """口径指纹，用于核对旧分析保存的统计口径。"""
        return f"{self.method.value}:{self.field_name} AS {self.alias}"

    def matches(self, method: AggregationMethod, field_name: str, alias: str) -> bool:
        return (
            self.method == method
            and self.field_name == field_name
            and self.alias == alias
        )


def aggregation_spec_for(metric: MetricDef) -> AggregationSpec:
    """聚合描述的选用入口：本地报告和多维查询都从这里取口径。"""
    return AggregationSpec(
        method=metric.aggregation,
        field_name=metric.field_name,
        alias=f"_{metric.metric_id}",
    )


# ============================================================
# 留存 SQL 的口径解析
# ============================================================

@dataclass(frozen=True)
class ParsedAggregation:
    """从留存 SQL 中解析出的一处聚合口径。"""
    method: AggregationMethod
    field_name: str
    alias: str


_SQL_PARSERS: list[tuple[AggregationMethod, re.Pattern[str]]] = [
    (AggregationMethod.COUNT_DISTINCT,
     re.compile(r"\bCOUNT\s*\(\s*DISTINCT\s+(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.P50,
     re.compile(r"\bPERCENTILE\s*\(\s*(\w+)\s*,\s*0\.5\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.P90,
     re.compile(r"\bPERCENTILE\s*\(\s*(\w+)\s*,\s*0\.9\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.P99,
     re.compile(r"\bPERCENTILE\s*\(\s*(\w+)\s*,\s*0\.99\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.SUM,
     re.compile(r"\bSUM\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.AVG,
     re.compile(r"\bAVG\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.COUNT,
     re.compile(r"\bCOUNT\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.MAX,
     re.compile(r"\bMAX\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
    (AggregationMethod.MIN,
     re.compile(r"\bMIN\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)", re.IGNORECASE)),
]


def parse_sql_aggregations(sql: str) -> list[ParsedAggregation]:
    """解析留存 SQL 中的全部聚合表达式（方式、字段、别名）。"""
    found: list[ParsedAggregation] = []
    for method, pattern in _SQL_PARSERS:
        for match in pattern.finditer(sql):
            found.append(ParsedAggregation(method, match.group(1), match.group(2)))
    return found


# ============================================================
# 口径版本登记
# ============================================================

@dataclass(frozen=True)
class SpecVersion:
    """一次口径登记：指标在某个版本下的聚合口径。"""
    metric_id: str
    metric_name: str
    version: int
    spec: AggregationSpec


@dataclass
class DashboardPlan:
    """一次看板分析计划：登记时钉住口径版本，确认后按原口径出数。"""
    plan_id: str
    pinned_versions: dict[str, int] = field(default_factory=dict)
    status: str = PLAN_PENDING
    confirm_count: int = 0

    @property
    def metric_id(self) -> str:
        return next(iter(self.pinned_versions), "")

    @property
    def spec_version(self) -> int | None:
        return next(iter(self.pinned_versions.values()), None)


class SpecRegistry:
    """口径登记处：登记指标口径版本，仲裁看板计划的确认、执行与恢复。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._versions: dict[str, list[SpecVersion]] = {}
        self._metrics: dict[str, MetricDef] = {}
        self._metric_names: dict[str, set[str]] = {}
        self._plans: dict[str, DashboardPlan] = {}

    # ---- 口径登记 ----

    def register(self, metric: MetricDef) -> SpecVersion:
        """登记指标当前口径；口径变化时版本号递增，口径未变则复用。"""
        with self._lock:
            spec = aggregation_spec_for(metric)
            history = self._versions.setdefault(metric.metric_id, [])
            self._metrics[metric.metric_id] = replace(metric)
            self._metric_names.setdefault(metric.metric_name, set()).add(metric.metric_id)
            if history and history[-1].spec == spec:
                return history[-1]
            version = history[-1].version + 1 if history else max(1, int(metric.version))
            spec_version = SpecVersion(metric.metric_id, metric.metric_name, version, spec)
            history.append(spec_version)
            return spec_version

    def current_version(self, metric_id: str) -> int | None:
        with self._lock:
            history = self._versions.get(metric_id, [])
            return history[-1].version if history else None

    def spec_for(self, metric_id: str, version: int) -> AggregationSpec | None:
        with self._lock:
            spec_version = self._version_of(metric_id, version)
            return spec_version.spec if spec_version else None

    def _version_of(self, metric_id: str, version: int) -> SpecVersion | None:
        for spec_version in self._versions.get(metric_id, []):
            if spec_version.version == version:
                return spec_version
        return None

    # ---- 看板计划 ----

    def begin_analysis(self, metric: MetricDef, plan_id: str | None = None) -> DashboardPlan:
        """登记指标并钉住口径版本，建立看板计划（此时尚未生成 SQL）。

        同一计划编号的重复提交返回既有计划，不会重建。
        """
        spec_version = self.register(metric)
        pid = plan_id or f"PLAN_{metric.metric_id}_v{spec_version.version}"
        with self._lock:
            plan = self._plans.get(pid)
            if plan is None:
                plan = DashboardPlan(
                    plan_id=pid,
                    pinned_versions={metric.metric_id: spec_version.version},
                )
                self._plans[pid] = plan
            return plan

    def get_plan(self, plan_id: str) -> DashboardPlan | None:
        with self._lock:
            return self._plans.get(plan_id)

    def confirm_plan(self, plan_id: str) -> DashboardPlan:
        """确认看板计划：并发提交同一份看板只确认一次。

        钉住的口径版本与当前登记版本不一致时，计划与未执行的看板冲突。
        """
        with self._lock:
            plan = self._plans[plan_id]
            if plan.status in (PLAN_CONFIRMED, PLAN_CONFLICT, PLAN_REVIEW):
                return plan
            for metric_id, version in plan.pinned_versions.items():
                history = self._versions.get(metric_id, [])
                if not history or history[-1].version != version:
                    plan.status = PLAN_CONFLICT
                    return plan
            plan.status = PLAN_CONFIRMED
            plan.confirm_count += 1
            return plan

    def run_plan(
        self,
        plan_id: str,
        rows: list[dict[str, Any]],
        *,
        dimensions: list[Any] | None = None,
        filters: dict[str, str] | None = None,
        order_by: str = "",
        time_range: str = "",
        query_id: str | None = None,
        query_name: str | None = None,
    ) -> dict[str, Any]:
        """执行看板计划：本地统计与 SQL 识别同一口径版本。

        已确认的计划按钉住版本出数（历史报告按原口径重算）；
        待执行的计划先确认，口径已被挤占时停在口径冲突；
        待核的计划不出数。
        """
        plan = self._plans[plan_id]
        if plan.status == PLAN_REVIEW:
            return {"status": PLAN_REVIEW, "plan_id": plan_id, "spec_version": None}
        if plan.status == PLAN_CONFLICT:
            return {
                "status": PLAN_CONFLICT,
                "plan_id": plan_id,
                "spec_version": plan.spec_version,
            }
        if plan.status == PLAN_PENDING:
            plan = self.confirm_plan(plan_id)
            if plan.status != PLAN_CONFIRMED:
                return {
                    "status": plan.status,
                    "plan_id": plan_id,
                    "spec_version": plan.spec_version,
                }

        with self._lock:
            pinned = dict(plan.pinned_versions)
            metrics = []
            overrides: dict[str, AggregationSpec] = {}
            for metric_id, version in pinned.items():
                spec_version = self._version_of(metric_id, version)
                if spec_version is None:
                    return {
                        "status": PLAN_REVIEW,
                        "plan_id": plan_id,
                        "spec_version": version,
                    }
                metrics.append(self._metrics[metric_id])
                overrides[metric_id] = spec_version.spec

        local_values = {
            metric_id: overrides[metric_id].compute_local(rows)
            for metric_id in pinned
        }
        query = OlapQuery(
            query_id=query_id or f"Q_{plan_id}",
            query_name=query_name or f"看板查询_{plan_id}",
            metrics=metrics,
            dimensions=list(dimensions or []),
            filters=dict(filters or {}),
            order_by=order_by,
            time_range=time_range,
            spec_overrides=overrides,
        )
        sql = query.build_sql()
        lead_metric = plan.metric_id
        return {
            "status": RUN_DONE,
            "plan_id": plan_id,
            "spec_version": plan.spec_version,
            "spec_versions": dict(pinned),
            "local_value": local_values.get(lead_metric),
            "local_values": local_values,
            "sql": sql,
            "alias": overrides[lead_metric].alias if lead_metric else "",
            "query": query,
        }

    # ---- 存量恢复 ----

    def restore_legacy_plan(
        self,
        plan_id: str,
        retained_metrics: list[dict[str, Any]],
    ) -> DashboardPlan:
        """恢复没有口径版本号的存量分析。

        每条指标需同时满足：指标身份唯一（指标 ID 或名称只对应一条登记
        血脉）、留存 SQL 的聚合方式在该血脉的版本中只匹配一个版本。
        任一歧义时，当次分析停在待核。
        """
        pinned: dict[str, int] = {}
        for entry in retained_metrics:
            spec_version = self._match_unique_version(entry)
            if spec_version is None:
                plan = DashboardPlan(plan_id=plan_id, status=PLAN_REVIEW)
                with self._lock:
                    self._plans[plan_id] = plan
                return plan
            pinned[spec_version.metric_id] = spec_version.version
        plan = DashboardPlan(
            plan_id=plan_id,
            pinned_versions=pinned,
            status=PLAN_CONFIRMED,
            confirm_count=1,
        )
        with self._lock:
            self._plans[plan_id] = plan
        return plan

    def _match_unique_version(self, entry: dict[str, Any]) -> SpecVersion | None:
        """指标身份与留存 SQL 聚合方式都唯一对上时才返回对应版本。"""
        metric_id = entry.get("metric_id")
        metric_name = entry.get("metric_name")
        retained_sql = entry.get("retained_sql", "")
        with self._lock:
            if metric_id and metric_id in self._versions:
                lineage_ids = [metric_id]
            elif metric_name:
                lineage_ids = sorted(self._metric_names.get(metric_name, set()))
            else:
                return None
            if len(lineage_ids) != 1:
                return None
            lineage = lineage_ids[0]
            expected_alias = f"_{lineage}"
            parsed = [
                agg for agg in parse_sql_aggregations(retained_sql)
                if agg.alias == expected_alias
            ]
            if len(parsed) != 1:
                return None
            agg = parsed[0]
            matches = [
                sv for sv in self._versions[lineage]
                if sv.spec.matches(agg.method, agg.field_name, agg.alias)
            ]
            if len(matches) != 1:
                return None
            return matches[0]
