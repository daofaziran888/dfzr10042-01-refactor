"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class RankingBoardService(BaseModuleService):
    MODULE = "ranking_board"
    ENTITY = "排行方案"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["方案编号", "排行指标", "排行维度", "时间范围", "TOP数量", "更新频率", "最后排行", "方案状态"]
    REQUIRED_FIELDS = ["方案编号", "排行指标", "排行维度"]
    STATUS_ORDER = ["待计算", "计算中", "已生成", "数据过期"]
    ACTION_RULES = {"启动计算": "计算中", "重算排行": "已生成", "标记过期": "数据过期"}
    NEGATIVE_ACTIONS = []
