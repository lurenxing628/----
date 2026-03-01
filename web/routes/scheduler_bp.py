from __future__ import annotations

from flask import Blueprint

from .enum_display import batch_status_zh, day_type_zh, priority_zh, ready_zh

# 统一蓝图对象：其它拆分文件通过 import bp 来注册路由
bp = Blueprint("scheduler", __name__)


def _priority_zh(v: str) -> str:
    return priority_zh(v)


def _ready_zh(v: str) -> str:
    return ready_zh(v)


def _batch_status_zh(v: str) -> str:
    return batch_status_zh(v)


def _day_type_zh(v: str) -> str:
    return day_type_zh(v)

