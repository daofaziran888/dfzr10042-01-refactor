"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class EventTrackService(BaseModuleService):
    MODULE = "event_track"
    ENTITY = "事件定义"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["事件编号", "事件名称", "事件属性", "触发条件", "归因键", "统计周期", "事件计数", "最后触发"]
    REQUIRED_FIELDS = ["事件编号", "事件名称", "事件属性"]
    STATUS_ORDER = ["草稿", "已上线", "Schema变更", "已下线"]
    ACTION_RULES = {"上线事件": "已上线", "标记变更": "Schema变更", "下线事件": "已下线"}
    NEGATIVE_ACTIONS = ["下线事件"]
