"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class QueryCacheService(BaseModuleService):
    MODULE = "query_cache"
    ENTITY = "缓存条目"
    OPERATION_TERM = "查询"
    LIST_FIELDS = ["条目编号", "查询哈希", "结果行数", "TTL秒数", "命中次数", "最后命中", "内存占用", "缓存状态"]
    REQUIRED_FIELDS = ["条目编号", "查询哈希", "结果行数"]
    STATUS_ORDER = ["有效", "即将过期", "已失效", "已驱逐"]
    ACTION_RULES = {"强制刷新": "有效", "标记失效": "即将过期", "清除缓存": "已失效"}
    NEGATIVE_ACTIONS = []
