"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DataExportService(BaseModuleService):
    MODULE = "data_export"
    ENTITY = "导出任务"
    OPERATION_TERM = "转换"
    LIST_FIELDS = ["任务编号", "数据来源", "导出格式", "字段筛选", "行数限制", "排序规则", "文件路径", "导出状态"]
    REQUIRED_FIELDS = ["任务编号", "数据来源", "导出格式"]
    STATUS_ORDER = ["待导出", "导出中", "已完成", "导出失败"]
    ACTION_RULES = {"启动导出": "导出中", "取消导出": "已完成", "重试导出": "导出失败"}
    NEGATIVE_ACTIONS = []
