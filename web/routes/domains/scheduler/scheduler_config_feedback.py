from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import flash

from core.services.scheduler.config.config_field_spec import field_label_for


def _normalized_error_fields(*, error_field: Optional[str], error_fields: Optional[List[str]]) -> List[str]:
    normalized = [str(item or "").strip() for item in list(error_fields or []) if str(item or "").strip()]
    fallback_field = str(error_field or "").strip()
    if not normalized and fallback_field:
        normalized = [fallback_field]
    return normalized


def _format_single_field_preset_error(detail: str, field_key: str) -> str:
    label = field_label_for(field_key)
    cleaned_detail = detail.replace(field_key, "").strip()
    cleaned_detail = cleaned_detail.lstrip("：:，,；; ")
    if not cleaned_detail:
        cleaned_detail = detail
    if cleaned_detail.startswith(label):
        return cleaned_detail
    return f"{label}：{cleaned_detail}"


def _format_preset_error_flash(
    *,
    error_field: Optional[str],
    error_fields: Optional[List[str]] = None,
    error_message: Optional[str],
) -> str:
    detail = str(error_message or "当前配置未保存为方案。").strip() or "当前配置未保存为方案。"
    normalized_fields = _normalized_error_fields(error_field=error_field, error_fields=error_fields)
    if not normalized_fields:
        return detail
    if len(normalized_fields) > 1:
        label_text = "、".join(dict.fromkeys(field_label_for(key) for key in normalized_fields))
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
        sample = "、".join(str(field) for field in adjusted_fields[:5])
        flash(
            f"方案已应用为：{effective or applied.get('requested_preset')}，但当前运行配置存在兼容修补或差异。"
            + (f" 涉及字段：{sample}。" if sample else ""),
            "warning",
        )
        return
    flash(f"已应用方案：{effective or applied.get('requested_preset')}", "success")


def _config_save_outcome_fields(outcome: Any, field_name: str) -> List[str]:
    return list(getattr(outcome, field_name, []) or [])


def _config_save_primary_flash(outcome: Any) -> Optional[Tuple[str, str]]:
    if _config_save_outcome_fields(outcome, "visible_changed_fields"):
        return "排产策略配置已保存。", "success"
    if _config_save_outcome_fields(outcome, "visible_repaired_fields"):
        return (
            "检测到页面字段兼容回退，已按当前表单值显式保存为自定义配置。",
            "warning",
        )
    if _config_save_outcome_fields(outcome, "hidden_repaired_fields"):
        return None
    if _config_save_outcome_fields(outcome, "blocked_hidden_repairs"):
        return None
    return "排产策略配置未发生变化。", "success"


def _iter_config_save_notice_messages(outcome: Any) -> List[str]:
    messages: List[str] = []
    for notice in list(getattr(outcome, "notices", []) or []):
        if not isinstance(notice, dict):
            continue
        kind = str(notice.get("kind") or "").strip().lower()
        if kind not in {"hidden", "blocked_hidden"}:
            continue
        message = str(notice.get("message") or "").strip()
        if message:
            messages.append(message)
    return messages


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
