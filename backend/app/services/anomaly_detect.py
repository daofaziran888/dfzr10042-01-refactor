"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class AnomalyDetectService(BaseModuleService):
    MODULE = "anomaly_detect"
    ENTITY = "检测规则"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["规则编号", "目标指标", "检测算法", "基线周期", "阈值倍数", "敏感度", "最近触发", "规则状态"]
    REQUIRED_FIELDS = ["规则编号", "目标指标", "检测算法"]
    STATUS_ORDER = ["待训练", "生效中", "已触发", "已关闭"]
    ACTION_RULES = {"启效规则": "生效中", "校准阈值": "已触发", "关闭规则": "已关闭"}
    NEGATIVE_ACTIONS = []
