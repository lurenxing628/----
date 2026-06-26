from __future__ import annotations

from typing import Any, Dict, List

from core.models.public_identifier_redaction import contains_internal_identifier
from core.models.scheduler_degradation_messages import public_degradation_events

PUBLIC_ATTEMPT_METRIC_KEYS = {
    "overdue_count",
    "weighted_tardiness_hours",
    "total_tardiness_hours",
    "makespan_hours",
    "changeover_count",
}
PUBLIC_SCORE_SCHEMA_KEYS = PUBLIC_ATTEMPT_METRIC_KEYS | {"failed_ops"}


def safe_metric_key(value: Any) -> str:
    key = str(value or "").strip()
    return key if key in PUBLIC_SCORE_SCHEMA_KEYS else ""


def public_int(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def safe_non_negative_int(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def public_float(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def safe_bool(value: Any) -> bool:
    return bool(value)


def safe_attempt_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or contains_internal_identifier(text):
        return ""
    return text


def safe_public_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = safe_attempt_text(item)
        if text and text not in out:
            out.append(text)
    return out


def project_attempt_score(value: Any) -> List[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, (int, float)) and not isinstance(item, bool)]


def project_attempt_failed_ops(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def project_attempt_metrics(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in PUBLIC_ATTEMPT_METRIC_KEYS:
        metric_value = value.get(key)
        if isinstance(metric_value, bool):
            continue
        if isinstance(metric_value, (int, float)):
            out[key] = metric_value
    return out


def project_public_metrics(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    for raw_key, metric_value in value.items():
        key = safe_attempt_text(raw_key)
        if not key:
            continue
        if isinstance(metric_value, bool):
            continue
        if isinstance(metric_value, (int, float)):
            out[key] = metric_value
    return out


def safe_counter_dict(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, int] = {}
    for key, raw in value.items():
        normalized_key = safe_attempt_text(key)
        if not normalized_key:
            continue
        try:
            count = int(raw or 0)
        except Exception:
            continue
        if count:
            out[normalized_key] = count
    return out


def project_degradation_event_list(events: Any) -> List[Dict[str, Any]]:
    if not isinstance(events, list):
        return []
    return public_degradation_events(events)


__all__ = [
    "PUBLIC_ATTEMPT_METRIC_KEYS",
    "PUBLIC_SCORE_SCHEMA_KEYS",
    "project_attempt_failed_ops",
    "project_attempt_metrics",
    "project_attempt_score",
    "project_degradation_event_list",
    "project_public_metrics",
    "safe_attempt_text",
    "safe_bool",
    "safe_counter_dict",
    "public_float",
    "public_int",
    "safe_metric_key",
    "safe_non_negative_int",
    "safe_public_text_list",
]
