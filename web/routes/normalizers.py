from __future__ import annotations

import json
from typing import Any, Dict, Optional

from flask import current_app

from core.infrastructure.errors import ValidationError
from core.models.enums import BatchPriority, CalendarDayType, ReadyStatus, YesNo
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_calendar_day_type_value,
    normalize_ready_status_value,
    normalize_yes_no_narrow_value,
)


def _normalize_batch_priority(value: Any) -> str:
    """
    批次优先级标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。
    """
    return normalize_batch_priority_value(
        value,
        default=BatchPriority.NORMAL.value,
        unknown_policy="passthrough",
    )


def _normalize_ready_status(value: Any) -> str:
    """
    齐套状态标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    约定：
    - 兼容中文：齐套/未齐套/部分齐套、是/否
    - 缺省：按 V1.1 规则视为 yes
    """
    return normalize_ready_status_value(
        value,
        default=ReadyStatus.YES.value,
        unknown_policy="passthrough",
    )


def _normalize_day_type(value: Any) -> str:
    """
    日历类型标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    - weekend/周末 -> holiday（统一口径）
    """
    return normalize_calendar_day_type_value(
        value,
        default=CalendarDayType.WORKDAY.value,
        unknown_policy="passthrough",
    )


def _normalize_operator_calendar_day_type(value: Any) -> str:
    """
    人员专属日历类型标准化：与 `_normalize_day_type` 同口径。
    """
    return _normalize_day_type(value)


def _normalize_yesno(value: Any) -> str:
    """
    yes/no 标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    约定：
    - 兼容中文：是/否
    - 缺省：yes
    """
    return normalize_yes_no_narrow_value(
        value,
        default=YesNo.YES.value,
        unknown_policy="passthrough",
    )


def normalize_version_or_latest_fallback(value: Any, *, latest_version: int) -> int:
    """
    latest-fallback 合同：空值、非整数、0、负数统一回退到最新版本。
    """
    latest = int(latest_version or 0)
    if value is None:
        return latest
    text = str(value).strip()
    if not text:
        return latest
    try:
        version = int(text)
    except Exception:
        return latest
    return version if version > 0 else latest


def normalize_version_or_latest(value: Any, *, latest_version: int) -> int:
    return normalize_version_or_latest_fallback(value, latest_version=latest_version)


def parse_optional_version_int(value: Any, *, field: str = "version") -> Optional[int]:
    """
    strict-int 合同：空值视为未提供；一旦提供，必须是整数。
    该入口不做 latest fallback，也不做正数约束。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception as exc:
        raise ValidationError(f"{field} 不合法（期望整数）", field=field) from exc


def _log_result_summary_warning(*, log_label: str, version: Any, source: Optional[str], issue: str, detail: str) -> None:
    if source is not None:
        current_app.logger.warning("%s result_summary %s（version=%s, source=%s, %s）", log_label, issue, version, source, detail)
        return
    current_app.logger.warning("%s result_summary %s（version=%s, %s）", log_label, issue, version, detail)


def _parse_result_summary_payload_with_meta(
    raw_summary: Any, *, version: Any, log_label: str, source: Optional[str] = None
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "payload": None,
        "parse_failed": False,
        "user_message": None,
        "reason": None,
    }
    if raw_summary is None or raw_summary == "":
        state["reason"] = "missing"
        return state
    if isinstance(raw_summary, dict):
        state["payload"] = raw_summary
        state["reason"] = "dict"
        return state
    if isinstance(raw_summary, list):
        _log_result_summary_warning(log_label=log_label, version=version, source=source, issue="结构不合法", detail="type=list")
        state["parse_failed"] = True
        state["reason"] = "invalid_structure"
        state["user_message"] = "当前版本的排产摘要结构异常，页面仅展示基础历史信息。"
        return state
    if not isinstance(raw_summary, str):
        _log_result_summary_warning(
            log_label=log_label,
            version=version,
            source=source,
            issue="结构不合法",
            detail=f"type={type(raw_summary).__name__}",
        )
        state["parse_failed"] = True
        state["reason"] = "invalid_structure"
        state["user_message"] = "当前版本的排产摘要结构异常，页面仅展示基础历史信息。"
        return state
    try:
        parsed = json.loads(str(raw_summary))
    except Exception as exc:
        _log_result_summary_warning(log_label=log_label, version=version, source=source, issue="解析失败", detail=f"error={exc.__class__.__name__}")
        state["parse_failed"] = True
        state["reason"] = "json_decode_error"
        state["user_message"] = "当前版本的排产摘要解析失败，页面仅展示基础历史信息。"
        return state
    if not isinstance(parsed, dict):
        _log_result_summary_warning(log_label=log_label, version=version, source=source, issue="结构不合法", detail=f"type={type(parsed).__name__}")
        state["parse_failed"] = True
        state["reason"] = "invalid_structure"
        state["user_message"] = "当前版本的排产摘要结构异常，页面仅展示基础历史信息。"
        return state
    state["payload"] = parsed
    state["reason"] = "json"
    return state


def _parse_result_summary_payload(
    raw_summary: Any, *, version: Any, log_label: str, source: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    return _parse_result_summary_payload_with_meta(
        raw_summary,
        version=version,
        log_label=log_label,
        source=source,
    ).get("payload")
