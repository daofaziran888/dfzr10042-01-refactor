"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class AttributionModelService(BaseModuleService):
    MODULE = "attribution_model"
    ENTITY = "归因模型"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["模型编号", "模型名称", "归因算法", "归因窗口", "归因维度", "分母事件", "分子事件", "模型状态"]
    REQUIRED_FIELDS = ["模型编号", "模型名称", "归因算法"]
    STATUS_ORDER = ["草稿", "生效中", "模型失效", "已停用"]
    ACTION_RULES = {"启效模型": "生效中", "标记失效": "模型失效", "停用模型": "已停用"}
    NEGATIVE_ACTIONS = ["停用模型"]
