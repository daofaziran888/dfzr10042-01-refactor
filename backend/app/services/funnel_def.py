"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class FunnelDefService(BaseModuleService):
    MODULE = "funnel_def"
    ENTITY = "漏斗方案"
    OPERATION_TERM = "计算"
    LIST_FIELDS = ["方案编号", "步骤序列", "转化窗口", "开始事件", "结束事件", "各步转化率", "总转化率", "方案状态"]
    REQUIRED_FIELDS = ["方案编号", "步骤序列", "转化窗口"]
    STATUS_ORDER = ["草稿", "已生成", "步骤缺失", "已归档"]
    ACTION_RULES = {"生成漏斗": "已生成", "标记缺失": "步骤缺失", "归档方案": "已归档"}
    NEGATIVE_ACTIONS = []
