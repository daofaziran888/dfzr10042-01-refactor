"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class AbExperimentService(BaseModuleService):
    MODULE = "ab_experiment"
    ENTITY = "实验方案"
    OPERATION_TERM = "归档"
    LIST_FIELDS = ["方案编号", "实验名称", "实验分组", "分流比例", "评估指标", "最小样本", "开始时间", "实验状态"]
    REQUIRED_FIELDS = ["方案编号", "实验名称", "实验分组"]
    STATUS_ORDER = ["设计期", "运行中", "已结束", "已终止"]
    ACTION_RULES = {"启动实验": "运行中", "终止实验": "已结束", "归档结果": "已终止"}
    NEGATIVE_ACTIONS = []
