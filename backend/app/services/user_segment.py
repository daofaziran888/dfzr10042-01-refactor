"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class UserSegmentService(BaseModuleService):
    MODULE = "user_segment"
    ENTITY = "比较方案"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["方案编号", "群体A", "群体B", "比较指标", "差异幅度", "显著性", "样本量A", "样本量B"]
    REQUIRED_FIELDS = ["方案编号", "群体A", "群体B"]
    STATUS_ORDER = ["待计算", "计算中", "已完成", "样本不足"]
    ACTION_RULES = {"启动计算": "计算中", "重算比较": "已完成", "标记不足": "样本不足"}
    NEGATIVE_ACTIONS = []
