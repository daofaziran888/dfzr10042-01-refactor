"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DataSnapshotService(BaseModuleService):
    MODULE = "data_snapshot"
    ENTITY = "数据快照"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["快照编号", "分析方案", "数据行数", "Schema摘要", "快照原因", "保留天数", "依赖版本", "创建时间"]
    REQUIRED_FIELDS = ["快照编号", "分析方案", "数据行数"]
    STATUS_ORDER = ["创建中", "可用", "标记中", "已过期"]
    ACTION_RULES = {"创建快照": "可用", "标记版本": "标记中", "清理过期": "已过期"}
    NEGATIVE_ACTIONS = []
