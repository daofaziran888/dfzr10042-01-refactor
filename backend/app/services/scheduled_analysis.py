"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ScheduledAnalysisService(BaseModuleService):
    MODULE = "scheduled_analysis"
    ENTITY = "调度任务"
    OPERATION_TERM = "调度"
    LIST_FIELDS = ["任务编号", "分析方案", "Cron表达式", "输出目标", "失败通知", "依赖检查", "并发上限", "下次执行"]
    REQUIRED_FIELDS = ["任务编号", "分析方案", "Cron表达式"]
    STATUS_ORDER = ["待激活", "执行中", "已完成", "已停用"]
    ACTION_RULES = {"激活任务": "执行中", "立即执行": "已完成", "停用任务": "已停用"}
    NEGATIVE_ACTIONS = ["停用任务"]
