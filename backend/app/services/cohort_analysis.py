"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class CohortAnalysisService(BaseModuleService):
    MODULE = "cohort_analysis"
    ENTITY = "同期群"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["群组编号", "群组名称", "划分周期", "起始事件", "回访事件", "观察窗口", "成员基数", "留存曲线"]
    REQUIRED_FIELDS = ["群组编号", "群组名称", "划分周期"]
    STATUS_ORDER = ["待计算", "计算中", "已生成", "数据不足"]
    ACTION_RULES = {"启动计算": "计算中", "重算群组": "已生成", "标记不足": "数据不足"}
    NEGATIVE_ACTIONS = []
