from __future__ import annotations

from flask import Blueprint

from core.models.enums import ReadyStatus

# 统一蓝图对象：其它拆分文件通过 import bp 来注册路由
bp = Blueprint("scheduler", __name__)


def _priority_zh(v: str) -> str:
    if v == "critical":
        return "特急"
    if v == "urgent":
        return "急件"
    return "普通"


def _ready_zh(v: str) -> str:
    if v == ReadyStatus.YES.value:
        return "齐套"
    if v == ReadyStatus.PARTIAL.value:
        return "部分齐套"
    return "未齐套"


def _batch_status_zh(v: str) -> str:
    if v == "pending":
        return "待排"
    if v == "scheduled":
        return "已排"
    if v == "processing":
        return "加工中"
    if v == "completed":
        return "已完成"
    if v == "cancelled":
        return "已取消"
    return v or "-"


def _day_type_zh(v: str) -> str:
    if v == "workday":
        return "工作日"
    # 统一：周末/节假日均视为“假期”
    if v in ("weekend", "holiday"):
        return "假期"
    return v or "-"

