"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ReportBuilderService(BaseModuleService):
    MODULE = "report_builder"
    ENTITY = "报告模板"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["模板编号", "报告名称", "引用指标", "排版格式", "生成周期", "推送渠道", "最近生成", "模板状态"]
    REQUIRED_FIELDS = ["模板编号", "报告名称", "引用指标"]
    STATUS_ORDER = ["草稿", "已发布", "格式异常", "已停用"]
    ACTION_RULES = {"发布模板": "已发布", "标记异常": "格式异常", "停用模板": "已停用"}
    NEGATIVE_ACTIONS = ["停用模板"]
