"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class OlapQueryService(BaseModuleService):
    MODULE = "olap_query"
    ENTITY = "查询方案"
    OPERATION_TERM = "查询"
    LIST_FIELDS = ["方案编号", "查询名称", "选择指标", "分组维度", "筛选条件", "排序规则", "时间范围", "查询状态"]
    REQUIRED_FIELDS = ["方案编号", "查询名称", "选择指标"]
    STATUS_ORDER = ["草稿", "已保存", "已共享", "已归档"]
    ACTION_RULES = {"保存方案": "已保存", "共享方案": "已共享", "归档方案": "已归档"}
    NEGATIVE_ACTIONS = []
