"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ExperimentResultService(BaseModuleService):
    MODULE = "experiment_result"
    ENTITY = "实验报告"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["报告编号", "关联实验", "指标名称", "对照组均值", "实验组均值", "提升幅度", "P值", "分析时间"]
    REQUIRED_FIELDS = ["报告编号", "关联实验", "指标名称"]
    STATUS_ORDER = ["待计算", "计算中", "已生成", "结果存疑"]
    ACTION_RULES = {"启动计算": "计算中", "重算校验": "已生成", "标记存疑": "结果存疑"}
    NEGATIVE_ACTIONS = []
