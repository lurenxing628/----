from __future__ import annotations

from typing import List, Optional, Sequence, Set

from flask import Blueprint, flash

from core.models.scheduler_degradation_messages import public_summary_warning_messages

from ...enum_display import batch_status_zh, day_type_zh, priority_zh, ready_zh


class _SchedulerBlueprint(Blueprint):
    def register(self, app, options):
        from .scheduler_route_registrar import register_scheduler_routes

        register_scheduler_routes()
        super().register(app, options)


# 统一蓝图对象；其余拆分文件通过 import bp 注册路由。
bp = _SchedulerBlueprint("scheduler", __name__)


def _priority_zh(v: str) -> str:
    return priority_zh(v)


def _ready_zh(v: str) -> str:
    return ready_zh(v)


def _batch_status_zh(v: str) -> str:
    return batch_status_zh(v)


def _day_type_zh(v: str) -> str:
    return day_type_zh(v)


def _normalize_warning_texts(values: object) -> List[str]:
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple)):
        raw_values = list(values)
    else:
        raw_values = []
    out: List[str] = []
    seen = set()
    for item in raw_values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _surface_schedule_warnings(
    messages: object,
    *,
    limit: int = 5,
    remaining_message: str = "另有 {remaining} 条提醒，请到系统管理里的排产历史查看这次排产的详细提醒。",
) -> None:
    warnings = _normalize_warning_texts(messages)
    if not warnings:
        return
    shown = warnings[: max(1, int(limit))]
    for item in shown:
        flash(item, "warning")
    remaining = len(warnings) - len(shown)
    if remaining > 0:
        flash(remaining_message.format(remaining=remaining), "warning")


def _surface_public_summary_warnings(
    messages: object,
    *,
    limit: int = 5,
    remaining_message: str = "另有 {remaining} 条提醒，请到系统管理里的排产历史查看这次排产的详细提醒。",
) -> None:
    raw_warnings = _normalize_warning_texts(messages)
    warnings = public_summary_warning_messages(messages)
    if not warnings and not raw_warnings:
        return
    shown = warnings[: max(1, int(limit))]
    for item in shown:
        flash(item, "warning")
    remaining_public = len(warnings) - len(shown)
    hidden_raw = sum(1 for item in raw_warnings if not public_summary_warning_messages([item]))
    if remaining_public > 0:
        flash(remaining_message.format(remaining=remaining_public), "warning")
    if hidden_raw > 0:
        flash(f"系统记录了 {hidden_raw} 条维护诊断，普通页面不展开；如需排查，请查看系统日志。", "warning")


def _surface_schedule_errors(
    messages: Optional[Sequence[str]],
    *,
    total: Optional[int] = None,
    limit: int = 5,
    category: str = "warning",
) -> None:
    errors = _normalize_warning_texts(list(messages or ()))
    if not errors and total is None:
        return
    shown = errors[: max(1, int(limit))]
    for item in shown:
        flash(item, category)
    total_count = len(errors) if total is None else max(int(total), 0)
    total_count = max(total_count, len(errors))
    remaining = total_count - len(shown)
    if remaining > 0:
        flash(f"另有 {remaining} 条错误，请到系统管理里的排产历史查看这次排产的详细提醒。", category)


def _secondary_degradation_message_text(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("message") or item.get("label") or "").strip()
    return str(item or "").strip()


def _suppressed_degradation_messages(messages: Optional[Sequence[str]]) -> Set[str]:
    suppressed = set(_normalize_warning_texts(list(messages or ())))
    suppressed.update(public_summary_warning_messages(list(messages or ())))
    return suppressed


def _is_secondary_degradation_suppressed(text: str, suppressed: Set[str], seen: Set[str]) -> bool:
    if not text or text in suppressed or text in seen:
        return True
    return any(public_text in suppressed for public_text in public_summary_warning_messages([text]))


def _surface_secondary_degradation_messages(
    messages: object,
    *,
    limit: int = 3,
    suppress_messages: Optional[Sequence[str]] = None,
) -> None:
    if not isinstance(messages, (list, tuple)):
        return
    suppressed = _suppressed_degradation_messages(suppress_messages)
    normalized: List[str] = []
    seen = set()
    for item in messages:
        text = _secondary_degradation_message_text(item)
        if _is_secondary_degradation_suppressed(text, suppressed, seen):
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
        flash(f"另有 {remaining} 条处理提示，请到系统管理里的排产历史查看这次排产的详细提醒。", "warning")
