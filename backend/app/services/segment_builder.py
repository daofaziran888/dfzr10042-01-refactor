"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class SegmentBuilderService(BaseModuleService):
    MODULE = "segment_builder"
    ENTITY = "人群包"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["人群编号", "人群名称", "圈选条件", "成员数量", "更新策略", "生效区间", "依赖指标", "最近计算"]
    REQUIRED_FIELDS = ["人群编号", "人群名称", "圈选条件"]
    STATUS_ORDER = ["草稿", "计算中", "可用", "已过期"]
    ACTION_RULES = {"启动计算": "计算中", "标记可用": "可用", "清理过期": "已过期"}
    NEGATIVE_ACTIONS = []
