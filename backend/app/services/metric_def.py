"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class MetricDefService(BaseModuleService):
    MODULE = "metric_def"
    ENTITY = "指标口径"
    OPERATION_TERM = "聚合"
    LIST_FIELDS = ["指标编号", "指标名称", "计算口径", "聚合方式", "数据来源", "统计周期", "负责人", "最近计算"]
    REQUIRED_FIELDS = ["指标编号", "指标名称", "计算口径"]
    STATUS_ORDER = ["草稿", "已发布", "口径变更", "已废弃"]
    ACTION_RULES = {"发布指标": "已发布", "标记变更": "口径变更", "废弃指标": "已废弃"}
    NEGATIVE_ACTIONS = []
