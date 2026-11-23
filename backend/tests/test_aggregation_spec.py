"""洞察工坊 · 聚合口径描述与口径版本登记测试

覆盖：
- 本地计算与多维查询共用聚合口径描述，Count、去重、分位数行为不变；
- 收入记录混入空值和无法转成数字的文本时，本地 Count/Sum 与 SQL 写法
  保持既定口径，不借重构统一成同一分母；
- 口径版本登记：看板计划钉住版本、并发提交只确认一次、历史报告按原口径
  重算、未执行看板与并发口径变更冲突；
- 无口径版本号的存量分析恢复：唯一对上才恢复，歧义停在待核；
- 离线指标计算与综合分析真实看板入口交错口径变更和查询执行。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.aggregation import (
    PLAN_CONFLICT,
    PLAN_CONFIRMED,
    PLAN_REVIEW,
    RUN_DONE,
    SpecRegistry,
    aggregation_spec_for,
    parse_sql_aggregations,
)
from app.analysis_pipeline import pipeline_metric_to_dashboard
from app.models import (
    AggregationMethod,
    DimensionDef,
    MetricDataSource,
    MetricDef,
    MetricPeriod,
    OlapQuery,
    ReportTemplate,
    _percentile,
)


# ============================================================
# 共享测试数据
# ============================================================

INCOME_ROWS = [
    {"income": 8},
    {"income": None},
    {"income": "abc"},  # 无法转成数字的文本
]


def make_metric(
    aggregation: AggregationMethod,
    metric_id: str = "M_REV",
    metric_name: str = "收入",
    field_name: str = "income",
) -> MetricDef:
    return MetricDef(
        metric_id=metric_id,
        metric_name=metric_name,
        calculation_formula=f"{aggregation.value}({field_name})",
        aggregation=aggregation,
        data_source=MetricDataSource.CLICKHOUSE,
        period=MetricPeriod.DAILY,
        owner="analyst",
        field_name=field_name,
        table_name="income_ledger",
    )


@pytest.fixture
def platform_dimension():
    return DimensionDef(
        dimension_id="D_PLATFORM",
        dimension_name="平台",
        field_source="platform",
        hierarchy_levels=["platform"],
    )


# ============================================================
# 共用聚合口径描述：两个入口行为不变
# ============================================================

class TestSharedAggregationSpec:
    def test_local_count_still_counts_rows(self):
        # 本地 Count 仍按本地行数计数：8、空值、文本共 3 行
        metric = make_metric(AggregationMethod.COUNT)
        assert metric.compute(INCOME_ROWS) == 3.0

    def test_local_sum_still_uses_numeric_values(self):
        # 本地 Sum 仍按可转数字的本地值求和：只有 8
        metric = make_metric(AggregationMethod.SUM)
        assert metric.compute(INCOME_ROWS) == 8.0

    def test_sql_count_keeps_original_field_and_alias(self):
        # SQL Count 仍使用原字段和别名，不借重构统一成同一分母
        metric = make_metric(AggregationMethod.COUNT)
        query = OlapQuery(query_id="Q1", query_name="收入计数", metrics=[metric])
        sql = query.build_sql()
        assert "COUNT(income) AS _M_REV" in sql
        assert "COUNT(*)" not in sql
        # 本地 Count=3（行数）与 SQL COUNT(income)（非空值计数）是两种既定口径
        assert metric.compute(INCOME_ROWS) == 3.0

    def test_sql_sum_keeps_original_expression_and_alias(self):
        metric = make_metric(AggregationMethod.SUM)
        query = OlapQuery(query_id="Q1", query_name="收入求和", metrics=[metric])
        assert "SUM(income) AS _M_REV" in query.build_sql()

    def test_count_distinct_both_entries(self):
        metric = make_metric(
            AggregationMethod.COUNT_DISTINCT, metric_id="M_DAU", field_name="user_id"
        )
        rows = [
            {"user_id": "u1"},
            {"user_id": "u2"},
            {"user_id": "u1"},
            {"user_id": None},
        ]
        assert metric.compute(rows) == 2.0
        query = OlapQuery(query_id="Q1", query_name="去重", metrics=[metric])
        assert "COUNT(DISTINCT user_id) AS _M_DAU" in query.build_sql()

    def test_percentiles_both_entries(self):
        rows = [{"income": float(v)} for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        for method, p, sql_part in [
            (AggregationMethod.P50, 50, "PERCENTILE(income, 0.5) AS _M_REV"),
            (AggregationMethod.P90, 90, "PERCENTILE(income, 0.9) AS _M_REV"),
            (AggregationMethod.P99, 99, "PERCENTILE(income, 0.99) AS _M_REV"),
        ]:
            metric = make_metric(method)
            assert metric.compute(rows) == _percentile([float(v) for v in range(1, 11)], p)
            query = OlapQuery(query_id="Q1", query_name="分位", metrics=[metric])
            assert sql_part in query.build_sql()

    def test_all_methods_select_same_spec_in_both_entries(self):
        rows = [
            {"income": 4.0}, {"income": 8.0}, {"income": 8.0}, {"income": None},
        ]
        for method in AggregationMethod:
            metric = make_metric(method)
            spec = aggregation_spec_for(metric)
            # 本地报告入口与共用口径描述结果一致
            assert metric.compute(rows) == spec.compute_local(rows)
            # 多维查询入口与共用口径描述表达式一致
            query = OlapQuery(query_id="Q1", query_name="统一", metrics=[metric])
            assert spec.sql_expression() in query.build_sql()

    def test_local_report_uses_shared_spec(self):
        # 本地报告（报告模板）经共用口径描述出数
        metric = make_metric(AggregationMethod.SUM)
        template = ReportTemplate(
            template_id="RPT_T",
            report_name="收入日报",
            referenced_metrics=[metric],
        )
        report = template.generate_report_data({"M_REV": INCOME_ROWS})
        assert report["metrics"]["M_REV"]["value"] == 8.0
        assert report["metrics"]["M_REV"]["aggregation"] == "sum"

    def test_empty_rows_keep_original_fallbacks(self):
        assert make_metric(AggregationMethod.COUNT).compute([]) == 0.0
        assert make_metric(AggregationMethod.SUM).compute([]) == 0.0
        assert make_metric(AggregationMethod.P90).compute([]) == 0.0


# ============================================================
# 口径版本登记
# ============================================================

class TestSpecRegistryVersions:
    def test_register_bumps_version_on_aggregation_change(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        v1 = registry.register(metric)
        assert v1.version == 1
        # 口径未变：复用版本
        again = registry.register(metric)
        assert again.version == 1
        # 改用去重计数：版本递增
        metric.aggregation = AggregationMethod.COUNT_DISTINCT
        v2 = registry.register(metric)
        assert v2.version == 2
        assert v2.spec.method == AggregationMethod.COUNT_DISTINCT
        assert registry.current_version("M_REV") == 2

    def test_historical_spec_versions_are_retained(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        registry.register(metric)
        metric.aggregation = AggregationMethod.COUNT_DISTINCT
        registry.register(metric)
        old_spec = registry.spec_for("M_REV", 1)
        assert old_spec is not None
        assert old_spec.method == AggregationMethod.SUM
        assert old_spec.compute_local(INCOME_ROWS) == 8.0


# ============================================================
# 看板计划：版本钉住、并发确认、冲突与历史重算
# ============================================================

class TestDashboardPlan:
    def test_unexecuted_plan_conflicts_with_concurrent_registration(self):
        # 已建好的看板查询尚未生成 SQL，另一进程将同一指标改用去重计数
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        plan = registry.begin_analysis(metric, plan_id="PLAN_STALE")
        assert plan.status == "待执行"
        assert plan.spec_version == 1

        other_process_metric = make_metric(AggregationMethod.COUNT_DISTINCT)
        registry.register(other_process_metric)  # 登记更新到 v2

        # 两个版本的登记更新与未执行的看板发生冲突
        confirmed = registry.confirm_plan(plan.plan_id)
        assert confirmed.status == PLAN_CONFLICT
        run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert run["status"] == PLAN_CONFLICT
        assert "local_value" not in run

    def test_local_and_sql_share_one_spec_version(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        plan = registry.begin_analysis(metric)
        run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert run["status"] == RUN_DONE
        assert run["spec_version"] == 1
        # 同一次看板分析：本地统计与 SQL 识别同一口径版本
        assert run["local_value"] == 8.0
        assert "SUM(income) AS _M_REV" in run["sql"]
        assert run["alias"] == "_M_REV"

    def test_concurrent_submit_confirms_only_once(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        plan = registry.begin_analysis(metric, plan_id="PLAN_CONCURRENT")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: registry.confirm_plan(plan.plan_id), range(16)))
        assert all(r.status == PLAN_CONFIRMED for r in results)
        # 并发提交同一份看板只确认一次
        assert registry.get_plan(plan.plan_id).confirm_count == 1

    def test_historical_report_recomputes_with_original_spec(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        plan = registry.begin_analysis(metric, plan_id="PLAN_HISTORY")
        first_run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert first_run["status"] == RUN_DONE
        assert first_run["spec_version"] == 1

        # 之后另一进程把指标改成去重计数（v2）
        registry.register(make_metric(AggregationMethod.COUNT_DISTINCT))
        assert registry.current_version("M_REV") == 2

        # 历史报告仍按原口径重算
        rerun = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert rerun["status"] == RUN_DONE
        assert rerun["spec_version"] == 1
        assert rerun["local_value"] == 8.0
        assert "SUM(income) AS _M_REV" in rerun["sql"]
        assert "COUNT(DISTINCT" not in rerun["sql"]


# ============================================================
# 存量分析恢复
# ============================================================

class TestLegacyRestore:
    def test_restore_uniquely_matched_plan(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        registry.register(metric)  # v1: SUM
        registry.register(make_metric(AggregationMethod.COUNT_DISTINCT))  # v2: 去重

        # 无口径版本号的存量分析：指标 ID 与留存 SQL 的聚合方式唯一对上 v1
        plan = registry.restore_legacy_plan("LEGACY_OK", [{
            "metric_id": "M_REV",
            "metric_name": "收入",
            "retained_sql": "SELECT SUM(income) AS _M_REV FROM income_ledger",
        }])
        assert plan.status == PLAN_CONFIRMED
        assert plan.spec_version == 1

        # 恢复后按原口径实际出数
        run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert run["status"] == RUN_DONE
        assert run["spec_version"] == 1
        assert run["local_value"] == 8.0
        assert "SUM(income) AS _M_REV" in run["sql"]

    def test_restore_ambiguous_same_name_metrics_stays_pending(self):
        registry = SpecRegistry()
        # 两条同名指标的登记血脉
        registry.register(make_metric(
            AggregationMethod.SUM, metric_id="M_REV_A", metric_name="收入"
        ))
        registry.register(make_metric(
            AggregationMethod.COUNT_DISTINCT, metric_id="M_REV_B", metric_name="收入"
        ))

        # 旧计划含两种同名指标、来路不可证（无指标 ID，别名对不上登记血脉）
        plan = registry.restore_legacy_plan("LEGACY_AMBIG", [
            {"metric_name": "收入",
             "retained_sql": "SELECT SUM(income) AS _legacy_1 FROM income_ledger"},
            {"metric_name": "收入",
             "retained_sql": "SELECT COUNT(DISTINCT income) AS _legacy_2 FROM income_ledger"},
        ])
        assert plan.status == PLAN_REVIEW

        # 歧义时当次分析停在待核，不出数
        run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert run["status"] == PLAN_REVIEW
        assert "local_value" not in run
        assert "sql" not in run

    def test_restore_sql_aggregation_mismatch_stays_pending(self):
        registry = SpecRegistry()
        registry.register(make_metric(AggregationMethod.SUM))  # 只有 SUM 血脉

        # 留存 SQL 的聚合方式（AVG）对不上任何登记版本
        plan = registry.restore_legacy_plan("LEGACY_MISMATCH", [{
            "metric_id": "M_REV",
            "metric_name": "收入",
            "retained_sql": "SELECT AVG(income) AS _M_REV FROM income_ledger",
        }])
        assert plan.status == PLAN_REVIEW

    def test_restore_repeated_aggregation_across_versions_stays_pending(self):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)
        registry.register(metric)  # v1: SUM
        metric.aggregation = AggregationMethod.COUNT_DISTINCT
        registry.register(metric)  # v2: 去重
        metric.aggregation = AggregationMethod.SUM
        registry.register(metric)  # v3: 又回到 SUM

        # 留存 SQL 的 SUM 同时对上 v1 和 v3，无法唯一确定口径版本
        plan = registry.restore_legacy_plan("LEGACY_REPEAT", [{
            "metric_id": "M_REV",
            "metric_name": "收入",
            "retained_sql": "SELECT SUM(income) AS _M_REV FROM income_ledger",
        }])
        assert plan.status == PLAN_REVIEW

    def test_parse_retained_sql_aggregations(self):
        parsed = parse_sql_aggregations(
            "SELECT platform, COUNT(DISTINCT user_id) AS _M_DAU, SUM(income) AS _M_REV "
            "FROM income_ledger GROUP BY platform"
        )
        by_alias = {agg.alias: agg for agg in parsed}
        assert by_alias["_M_DAU"].method == AggregationMethod.COUNT_DISTINCT
        assert by_alias["_M_DAU"].field_name == "user_id"
        assert by_alias["_M_REV"].method == AggregationMethod.SUM
        assert by_alias["_M_REV"].field_name == "income"


# ============================================================
# 真实入口交错：离线指标计算 + 综合分析看板入口
# ============================================================

class TestRealEntriesInterleaved:
    def test_interleave_spec_changes_and_query_executions(self, platform_dimension):
        registry = SpecRegistry()
        metric = make_metric(AggregationMethod.SUM)

        # 离线指标计算：仍按本地值计数
        assert metric.compute(INCOME_ROWS) == 8.0

        # 综合分析真实看板入口：v1 出数
        r1 = pipeline_metric_to_dashboard(
            [metric], [platform_dimension], INCOME_ROWS, registry=registry
        )
        d1 = r1["dashboards"][0]
        assert d1["status"] == RUN_DONE
        assert d1["spec_version"] == 1
        assert d1["computed_value"] == 8.0
        assert "SUM(income) AS _M_REV" in d1["sql"]

        # 口径变更：同一指标改用去重计数
        metric.aggregation = AggregationMethod.COUNT_DISTINCT
        assert metric.compute(INCOME_ROWS) == 2.0  # 本地去重：{8, "abc"}

        # 看板入口再次执行：识别 v2 口径
        r2 = pipeline_metric_to_dashboard(
            [metric], [platform_dimension], INCOME_ROWS, registry=registry
        )
        d2 = r2["dashboards"][0]
        assert d2["status"] == RUN_DONE
        assert d2["spec_version"] == 2
        assert d2["computed_value"] == 2.0
        assert "COUNT(DISTINCT income) AS _M_REV" in d2["sql"]

        # 已建好的看板计划尚未生成 SQL 时口径再次变更 → 冲突
        plan = registry.begin_analysis(metric, plan_id="PLAN_LATE")  # 钉住 v2
        metric.aggregation = AggregationMethod.AVG
        registry.register(metric)  # v3
        late_run = registry.run_plan(plan.plan_id, INCOME_ROWS)
        assert late_run["status"] == PLAN_CONFLICT

        # v1 的历史看板仍按原口径重算
        history_run = registry.run_plan("PLAN_M_REV_v1", INCOME_ROWS)
        assert history_run["status"] == RUN_DONE
        assert history_run["local_value"] == 8.0
        assert "SUM(income) AS _M_REV" in history_run["sql"]

    def test_dashboard_entry_without_registry_is_unchanged(self, platform_dimension):
        # 既有输入输出不变：不传登记处时结果结构与取值与原来一致
        metric = make_metric(AggregationMethod.SUM)
        result = pipeline_metric_to_dashboard(
            [metric], [platform_dimension], INCOME_ROWS
        )
        dash = result["dashboards"][0]
        assert set(dash.keys()) == {
            "dashboard_id", "dashboard_name", "metric_name",
            "computed_value", "sql", "cache_hit", "chart_count",
        }
        assert dash["computed_value"] == 8.0
        assert "SUM(income) AS _M_REV" in dash["sql"]
        assert result["total_cached_queries"] == 1

    def test_offline_and_dashboard_entries_agree(self, platform_dimension):
        # 离线指标计算与看板入口的本地统计一致，SQL 与直接拼接一致
        metric = make_metric(AggregationMethod.P90)
        rows = [{"income": float(v)} for v in range(1, 11)]
        result = pipeline_metric_to_dashboard([metric], [platform_dimension], rows)
        dash = result["dashboards"][0]
        assert dash["computed_value"] == metric.compute(rows)
        direct_sql = OlapQuery(
            query_id="Q_M_REV",
            query_name="查询_收入",
            metrics=[metric],
            dimensions=[platform_dimension],
            filters={"status": "已发布"},
            order_by="income DESC",
            time_range="daily",
        ).build_sql()
        assert dash["sql"] == direct_sql
