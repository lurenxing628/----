from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import current_app

from core.infrastructure.errors import ValidationError
from core.models.enums import BatchPriority, CalendarDayType, ReadyStatus, YesNo
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_calendar_day_type_value,
    normalize_ready_status_value,
    normalize_yes_no_narrow_value,
)
from core.services.scheduler.history_summary_parser import parse_result_summary_payload
from web.viewmodels.scheduler_history_summary import (
    decorate_history_version_options as _decorate_history_version_options,
)
from web.viewmodels.scheduler_history_summary import (
    parse_state_from_result,
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
    result = parse_result_summary_payload(raw_summary)
    state = parse_state_from_result(result)
    if result.parse_failed:
        issue = "解析失败" if result.reason == "json_decode_error" else "结构不合法"
        detail = "error=JSONDecodeError" if result.reason == "json_decode_error" else f"type={result.raw_type}"
        _log_result_summary_warning(
            log_label=log_label,
            version=version,
            source=source,
            issue=issue,
            detail=detail,
        )
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


def decorate_history_version_options(
    versions: Any,
    *,
    log_label: str,
    source: str = "version_option",
) -> List[Dict[str, Any]]:
    decorated = _decorate_history_version_options(versions)
    for row in decorated:
        _parse_result_summary_payload_with_meta(
            row.get("result_summary"),
            version=row.get("version"),
            log_label=log_label,
            source=source,
        )
    return decorated
