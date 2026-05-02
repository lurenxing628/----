from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import flash

from core.services.scheduler.config import ConfigService

from .scheduler_config_display_state import public_hidden_repair_notice, public_meta_parse_warning


def _normalized_error_fields(*, error_field: Optional[str], error_fields: Optional[List[str]]) -> List[str]:
    normalized = [str(item or "").strip() for item in list(error_fields or []) if str(item or "").strip()]
    fallback_field = str(error_field or "").strip()
    if not normalized and fallback_field:
        normalized = [fallback_field]
    return normalized


def _format_single_field_preset_error(detail: str, field_key: str) -> str:
    label = ConfigService.get_field_label(field_key)
    cleaned_detail = detail.replace(field_key, "").strip()
    cleaned_detail = cleaned_detail.lstrip("：:，,；; ")
    if not cleaned_detail:
        cleaned_detail = detail
    if cleaned_detail.startswith(label):
        return cleaned_detail
    return f"{label}：{cleaned_detail}"


def _replace_field_keys_with_labels(detail: str, field_keys: List[str]) -> str:
    text = str(detail or "")
    for field_key in sorted({str(item or "").strip() for item in field_keys if str(item or "").strip()}, key=len, reverse=True):
        label = ConfigService.get_field_label(field_key)
        if label and label != field_key:
            text = text.replace(field_key, label)
    return text


def _format_preset_error_flash(
    *,
    error_field: Optional[str],
    error_fields: Optional[List[str]] = None,
    error_message: Optional[str],
) -> str:
    detail = str(error_message or "当前配置未保存为方案。").strip() or "当前配置未保存为方案。"
    normalized_fields = _normalized_error_fields(error_field=error_field, error_fields=error_fields)
    detail = _replace_field_keys_with_labels(detail, normalized_fields)
    if not normalized_fields:
        return detail
    if len(normalized_fields) > 1:
        label_text = "、".join(dict.fromkeys(ConfigService.get_field_label(key) for key in normalized_fields))
        if not label_text or detail.startswith(label_text):
            return detail
        return f"{label_text}：{detail}"
    return _format_single_field_preset_error(detail, normalized_fields[0])


def _flash_preset_apply_feedback(applied: Dict[str, Any]) -> None:
    status = str(applied.get("status") or "").strip().lower()
    effective = str(applied.get("effective_active_preset") or "").strip()
    adjusted_fields = list(applied.get("adjusted_fields") or [])
    if status == "rejected":
        error_field = str(applied.get("error_field") or "").strip()
        error_fields = list(applied.get("error_fields") or [])
        error_message = str(applied.get("error_message") or "当前方案未应用。").strip()
        flash(
            _format_preset_error_flash(
                error_field=error_field,
                error_fields=error_fields,
                error_message=f"当前方案未应用。 {error_message}".strip(),
            ),
            "error",
        )
        return
    if status == "adjusted" and adjusted_fields:
        sample = "、".join(ConfigService.public_config_field_labels([str(field) for field in adjusted_fields[:5]]))
        flash(
            f"方案已应用为：{effective or applied.get('requested_preset')}，但其中几项设置不能直接使用，系统已改成可保存的默认值。"
            + (f" 请检查这些设置：{sample}。" if sample else ""),
            "warning",
        )
        return
    flash(f"已应用方案：{effective or applied.get('requested_preset')}", "success")


def _config_save_outcome_fields(outcome: Any, field_name: str) -> List[str]:
    return list(getattr(outcome, field_name, []) or [])


def _config_save_primary_flash(outcome: Any) -> Optional[Tuple[str, str]]:
    if str(getattr(outcome, "status", "") or "").strip() == "blocked_hidden_repair":
        return None
    if _config_save_outcome_fields(outcome, "blocked_hidden_repairs"):
        return None
    if _config_save_outcome_fields(outcome, "visible_changed_fields"):
        return "排产策略配置已保存。", "success"
    if _config_save_outcome_fields(outcome, "visible_repaired_fields"):
        return (
            "页面字段已按当前可保存取值更新，并保存为自定义配置。",
            "warning",
        )
    if _config_save_outcome_fields(outcome, "hidden_repaired_fields"):
        return None
    return "排产策略配置未发生变化。", "success"


def _public_notice_messages(public_payload: Dict[str, Any]) -> List[str]:
    messages: List[str] = []
    for notice in list(public_payload.get("notices") or []):
        if not isinstance(notice, dict):
            continue
        message = str(notice.get("message") or "").strip()
        if message:
            messages.append(message)
    return messages


def _meta_parse_warning_messages(outcome: Any) -> List[str]:
    return [public_meta_parse_warning() for warning in list(getattr(outcome, "meta_parse_warnings", []) or []) if isinstance(warning, dict)]


def _legacy_notice_messages(outcome: Any) -> List[str]:
    messages: List[str] = []
    for notice in list(getattr(outcome, "notices", []) or []):
        if not isinstance(notice, dict):
            continue
        kind = str(notice.get("kind") or "").strip().lower()
        if kind not in {"hidden", "blocked_hidden"}:
            continue
        fields = [str(item or "").strip() for item in list(notice.get("fields") or []) if str(item or "").strip()]
        messages.append(public_hidden_repair_notice(fields, blocked=kind == "blocked_hidden"))
    return messages


def _iter_config_save_notice_messages(outcome: Any) -> List[str]:
    to_public = getattr(outcome, "to_public_outcome_dict", None)
    public_payload = to_public() if callable(to_public) else None
    if isinstance(public_payload, dict):
        return _public_notice_messages(public_payload) + _meta_parse_warning_messages(outcome)
    return _legacy_notice_messages(outcome) + _meta_parse_warning_messages(outcome)


def _flash_config_save_outcome(outcome: Any) -> None:
    primary_flash = _config_save_primary_flash(outcome)
    if primary_flash is not None:
        message, category = primary_flash
        flash(message, category)
    for message in _iter_config_save_notice_messages(outcome):
        flash(message, "warning")


__all__ = [
    "_flash_config_save_outcome",
    "_flash_preset_apply_feedback",
    "_format_preset_error_flash",
]
