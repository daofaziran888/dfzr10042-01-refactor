"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class MetricCompareService(BaseModuleService):
    MODULE = "metric_compare"
    ENTITY = "对比方案"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["方案编号", "主指标", "对比指标", "对比周期", "基准值", "当前值", "变化幅度", "对比状态"]
    REQUIRED_FIELDS = ["方案编号", "主指标", "对比指标"]
    STATUS_ORDER = ["待计算", "计算中", "已完成", "数据缺失"]
    ACTION_RULES = {"启动计算": "计算中", "重算对比": "已完成", "标记缺失": "数据缺失"}
    NEGATIVE_ACTIONS = []
