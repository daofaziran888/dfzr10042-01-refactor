"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DashboardDefService(BaseModuleService):
    MODULE = "dashboard_def"
    ENTITY = "数据看板"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["看板编号", "看板名称", "布局配置", "订阅用户", "刷新策略", "缓存TTL", "最近刷新", "看板状态"]
    REQUIRED_FIELDS = ["看板编号", "看板名称", "布局配置"]
    STATUS_ORDER = ["草稿", "已发布", "需更新", "已下架"]
    ACTION_RULES = {"发布看板": "已发布", "标记更新": "需更新", "下架看板": "已下架"}
    NEGATIVE_ACTIONS = []
