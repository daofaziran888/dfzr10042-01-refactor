"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DrillPathService(BaseModuleService):
    MODULE = "drill_path"
    ENTITY = "下钻方案"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["方案编号", "父级维度", "子级维度", "过渡层数", "数据粒度", "预计算模式", "最近下钻", "方案状态"]
    REQUIRED_FIELDS = ["方案编号", "父级维度", "子级维度"]
    STATUS_ORDER = ["草稿", "生效中", "粒度冲突", "已停用"]
    ACTION_RULES = {"启效方案": "生效中", "标记冲突": "粒度冲突", "停用方案": "已停用"}
    NEGATIVE_ACTIONS = ["停用方案"]
