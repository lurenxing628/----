from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .ui_presenters import UiDetailsNotice, UiNotice


def build_config_notice_items(
    *,
    config_degraded_field_labels: Sequence[str],
    config_hidden_warnings: Sequence[str],
) -> Tuple[UiDetailsNotice, ...]:
    notices: List[UiDetailsNotice] = []
    if config_degraded_field_labels:
        notices.append(
            UiDetailsNotice(
                "当前配置需要复核",
                f"当前配置有 {len(config_degraded_field_labels)} 个需要复核的修正项。",
                tone="warning",
                detail_label="查看修正项",
                detail_items=tuple(str(item) for item in config_degraded_field_labels),
                role="status",
                aria_live="polite",
            )
        )
    if config_hidden_warnings:
        notices.append(
            UiDetailsNotice(
                "平时不直接显示的设置需要检查",
                f"还有 {len(config_hidden_warnings)} 条平时不直接显示的设置需要检查。",
                tone="warning",
                detail_label="查看处理提示",
                detail_items=tuple(str(item) for item in config_hidden_warnings),
                role="status",
                aria_live="polite",
            )
        )
    return tuple(notices)


def normalize_warning_texts(values: Any) -> List[str]:
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


def latest_warning_state(
    *,
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_display: Dict[str, Any],
) -> Tuple[List[str], int, int]:
    latest_warning_messages = normalize_warning_texts(
        (latest_summary or {}).get("warnings") if isinstance(latest_summary, dict) else None
    )
    latest_warning_preview = list(latest_summary_display.get("warnings_preview") or [])
    if not latest_warning_preview and not latest_summary_display.get("warning_total"):
        latest_warning_preview = latest_warning_messages[:3]
    latest_warning_total = int(latest_summary_display.get("warning_total") or len(latest_warning_messages))
    latest_warning_hidden_count = int(
        latest_summary_display.get("warning_hidden_count") or max(0, latest_warning_total - len(latest_warning_preview))
    )
    return latest_warning_preview, latest_warning_total, latest_warning_hidden_count


def latest_parse_notice_items(latest_summary_display: Dict[str, Any]) -> Tuple[UiNotice, ...]:
    parse_state = latest_summary_display.get("summary_parse_state") or {}
    if not parse_state.get("parse_failed"):
        return ()
    message = str(parse_state.get("user_message") or "").strip()
    if not message:
        return ()
    return (UiNotice("排产历史摘要解析异常", message, tone="warning", role="status", aria_live="polite"),)


def _format_degradation_message(item: Dict[str, Any]) -> str:
    label = str(item.get("label") or "").strip()
    message = str(item.get("message") or "").strip()
    if label and message:
        return f"{label}：{message}"
    return label or message


def latest_detail_notice_items(
    *,
    latest_summary_display: Dict[str, Any],
    latest_warning_preview: Sequence[str],
    latest_warning_total: int,
    latest_warning_hidden_count: int,
) -> Tuple[UiDetailsNotice, ...]:
    notices: List[UiDetailsNotice] = []
    primary_degradation = latest_summary_display.get("primary_degradation") or {}
    primary_message = str(primary_degradation.get("message") or "").strip()
    primary_details = tuple(str(item) for item in primary_degradation.get("details") or [])
    if primary_message:
        notices.append(
            UiDetailsNotice(
                "排产过程需要注意",
                primary_message,
                tone="warning",
                detail_label=f"查看 {len(primary_details)} 条明细",
                detail_items=primary_details,
                role="status",
                aria_live="polite",
            )
        )

    other_messages = tuple(
        message
        for message in (
            _format_degradation_message(item)
            for item in latest_summary_display.get("display_secondary_degradation_messages") or []
            if isinstance(item, dict)
        )
        if message
    )
    if other_messages:
        notices.append(
            UiDetailsNotice(
                "其他需要注意的排产提示",
                "这些提示不会阻止你查看快照，但建议排产前一起复核。",
                tone="warning",
                detail_label=f"查看 {len(other_messages)} 条提示",
                detail_items=other_messages,
                role="status",
                aria_live="polite",
            )
        )

    if latest_warning_total:
        footer = ""
        if latest_warning_hidden_count > 0:
            footer = f"另有 {latest_warning_hidden_count} 条提醒，请到系统历史查看。"
        notices.append(
            UiDetailsNotice(
                "排产提醒",
                f"提醒：{latest_warning_total} 条",
                tone="warning",
                detail_label=f"查看前 {len(latest_warning_preview)} 条提醒",
                detail_items=tuple(str(item) for item in latest_warning_preview),
                footer=footer,
                role="status",
                aria_live="polite",
            )
        )
    return tuple(notices)


__all__ = [
    "build_config_notice_items",
    "latest_detail_notice_items",
    "latest_parse_notice_items",
    "latest_warning_state",
    "normalize_warning_texts",
]
