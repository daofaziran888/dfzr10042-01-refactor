"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DatasetJoinService(BaseModuleService):
    MODULE = "dataset_join"
    ENTITY = "关联方案"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["方案编号", "主数据集", "关联数据集", "关联键", "连接类型", "字段映射", "结果行数", "方案状态"]
    REQUIRED_FIELDS = ["方案编号", "主数据集", "关联数据集"]
    STATUS_ORDER = ["草稿", "已执行", "字段冲突", "已清理"]
    ACTION_RULES = {"执行关联": "已执行", "标记冲突": "字段冲突", "清理方案": "已清理"}
    NEGATIVE_ACTIONS = []
