from __future__ import annotations

from typing import List, Optional, Sequence

from flask import Blueprint, flash

from ...enum_display import batch_status_zh, day_type_zh, priority_zh, ready_zh

# 统一蓝图对象；其余拆分文件通过 import bp 注册路由。
bp = Blueprint("scheduler", __name__)


def _priority_zh(v: str) -> str:
    return priority_zh(v)


def _ready_zh(v: str) -> str:
    return ready_zh(v)


def _batch_status_zh(v: str) -> str:
    return batch_status_zh(v)


def _day_type_zh(v: str) -> str:
    return day_type_zh(v)


def _normalize_warning_texts(values: object) -> List[str]:
    if not isinstance(values, (list, tuple)):
        return []
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _surface_schedule_warnings(messages: object, *, limit: int = 5) -> None:
    warnings = _normalize_warning_texts(messages)
    if not warnings:
        return
    shown = warnings[: max(1, int(limit))]
    for item in shown:
        flash(item, "warning")
    remaining = len(warnings) - len(shown)
    if remaining > 0:
        flash(f"另有 {remaining} 条告警，请到系统历史查看。", "warning")


def _surface_schedule_errors(messages: Optional[Sequence[str]], *, total: Optional[int] = None, limit: int = 5) -> None:
    errors = _normalize_warning_texts(list(messages or ()))
    if not errors and total is None:
        return
    shown = errors[: max(1, int(limit))]
    for item in shown:
        flash(item, "warning")
    total_count = len(errors) if total is None else max(int(total), 0)
    total_count = max(total_count, len(errors))
    remaining = total_count - len(shown)
    if remaining > 0:
        flash(f"另有 {remaining} 条错误，请到系统历史查看。", "warning")


def _surface_secondary_degradation_messages(
    messages: object,
    *,
    limit: int = 3,
    suppress_messages: Optional[Sequence[str]] = None,
) -> None:
    if not isinstance(messages, (list, tuple)):
        return
    suppressed = set(_normalize_warning_texts(list(suppress_messages or ())))
    normalized: List[str] = []
    seen = set()
    for item in messages:
        text = ""
        if isinstance(item, dict):
            text = str(item.get("message") or item.get("label") or "").strip()
        else:
            text = str(item or "").strip()
        if not text or text in suppressed or text in seen:
            continue
        seen.add(text)
        normalized.append(text)

    if not normalized:
        return
    shown = normalized[: max(1, int(limit))]
    for item in shown:
        flash(item, "warning")
    remaining = len(normalized) - len(shown)
    if remaining > 0:
        flash(f"另有 {remaining} 条降级说明，请到系统历史查看。", "warning")
