"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DimensionDefService(BaseModuleService):
    MODULE = "dimension_def"
    ENTITY = "分析维度"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["维度编号", "维度名称", "字段来源", "层级结构", "枚举值数", "关联指标数", "最近刷新", "维度状态"]
    REQUIRED_FIELDS = ["维度编号", "维度名称", "字段来源"]
    STATUS_ORDER = ["草稿", "生效中", "值域变更", "已停用"]
    ACTION_RULES = {"启效维度": "生效中", "标记变更": "值域变更", "停用维度": "已停用"}
    NEGATIVE_ACTIONS = ["停用维度"]
