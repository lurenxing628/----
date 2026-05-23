from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

SAMPLE_LIMIT = 5

STATUS_LABELS = {
    "ok": "正常",
    "notice": "提示",
    "warning": "需要关注",
    "danger": "存在风险",
    "unavailable": "不可用",
    "error": "诊断异常",
    "empty": "暂无可分析",
    "unknown": "状态未知",
}

GRAPH_STATUS_LABELS = {
    "available": "可用",
    "unavailable": "不可用",
    "input_error": "输入异常",
    "build_error": "构图异常",
}

LEVEL_RANK = {
    "unknown": 0,
    "ok": 1,
    "notice": 2,
    "warning": 3,
    "danger": 4,
}


def list_or_empty(value: Optional[Iterable[Any]]) -> List[Any]:
    if value is None:
        return []
    return list(value)


def build_item(
    *,
    key: str,
    label: str,
    value: Any = None,
    level: str = "unknown",
    message: str = "",
    details: Optional[Iterable[Any]] = None,
    links: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "key": str(key or ""),
        "label": str(label or ""),
        "value": value,
        "level": str(level or "unknown"),
        "message": str(message or ""),
        "details": list_or_empty(details),
        "links": list_or_empty(links),
    }


def build_section(
    *,
    key: str,
    title: str,
    status: str = "unknown",
    status_label: str = "",
    summary: str = "",
    items: Optional[Iterable[Dict[str, Any]]] = None,
    links: Optional[Iterable[Dict[str, Any]]] = None,
    degraded: bool = False,
    degradation_events: Optional[Iterable[Dict[str, Any]]] = None,
    empty_reason: str = "",
) -> Dict[str, Any]:
    return {
        "key": str(key or ""),
        "title": str(title or ""),
        "status": str(status or "unknown"),
        "status_label": str(status_label or ""),
        "summary": str(summary or ""),
        "items": list_or_empty(items),
        "links": list_or_empty(links),
        "degraded": bool(degraded),
        "degradation_events": list_or_empty(degradation_events),
        "empty_reason": str(empty_reason or ""),
    }


def safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def safe_list(value: Any) -> List[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


class NonFiniteDiagnosticNumber(ValueError):
    """诊断摘要中的数字不是有限值。"""


def _raise_non_finite_number(value: Any) -> None:
    raise NonFiniteDiagnosticNumber(f"诊断摘要包含非有限数字，无法安全展示：{value!r}")


def _ensure_finite_number(number: float, original: Any) -> None:
    if not math.isfinite(number):
        _raise_non_finite_number(original)


def _reject_non_finite_text(value: str) -> None:
    text = value.strip()
    if not text:
        return
    if text.lstrip("+-").isdigit():
        return
    try:
        number = float(text)
    except ValueError:
        return
    _ensure_finite_number(number, value)


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return int(default)
    if isinstance(value, float):
        _ensure_finite_number(value, value)
    elif isinstance(value, str):
        _reject_non_finite_text(value)
    try:
        return int(value)
    except OverflowError as exc:
        raise NonFiniteDiagnosticNumber(f"诊断摘要包含非有限整数，无法安全展示：{value!r}") from exc
    except (TypeError, ValueError):
        return int(default)


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    try:
        number = float(value)
    except OverflowError as exc:
        raise NonFiniteDiagnosticNumber(f"诊断摘要包含非有限小数，无法安全展示：{value!r}") from exc
    except (TypeError, ValueError):
        return float(default)
    _ensure_finite_number(number, value)
    return number


def graph_public(selected_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = safe_dict(selected_summary)
    algo = safe_dict(summary.get("algo"))
    return safe_dict(algo.get("graph_analysis"))


def graph_diagnostics(selected_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = safe_dict(selected_summary)
    diagnostics = safe_dict(summary.get("diagnostics"))
    return safe_dict(diagnostics.get("graph_analysis"))


def summary_counts(selected_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return safe_dict(safe_dict(selected_summary).get("counts"))


def normalize_level(level: Any) -> str:
    text = str(level or "").strip()
    if text in LEVEL_RANK:
        return text
    if text in {"error", "unavailable"}:
        return "danger"
    if text == "empty":
        return "notice"
    return "unknown"


def section_status_from_levels(levels: Iterable[str]) -> str:
    normalized = [normalize_level(level) for level in levels]
    if not normalized:
        return "unknown"
    worst = max(normalized, key=lambda level: LEVEL_RANK.get(level, 0))
    return worst if worst != "unknown" else "unknown"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, STATUS_LABELS["unknown"])


def level_if(condition: bool, true_level: str, false_level: str) -> str:
    return true_level if condition else false_level


def text_if(condition: bool, true_text: str, false_text: str) -> str:
    return true_text if condition else false_text


def detail_from_samples(prefix: str, samples: Sequence[str]) -> List[str]:
    if not samples:
        return []
    return [f"{prefix}{'、'.join(samples)}"]


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, dict):
        if "unsupported_value_type" in value or "unsupported_data_type" in value:
            return "维护诊断样本已省略"
        sample = value.get("text_sample")
        if isinstance(sample, str):
            return sample.strip()
    return ""


def sample_text_values(values: Any, limit: int = SAMPLE_LIMIT) -> List[str]:
    out: List[str] = []
    for value in safe_list(values):
        text = safe_text(value)
        if text:
            out.append(text)
        if len(out) >= int(limit):
            break
    return out


def format_count(value: int, unit: str) -> str:
    return f"{int(value)} {unit}"


def format_minutes(minutes: int) -> str:
    value = int(minutes)
    if value <= 0:
        return "0 分钟"
    if value % 60 == 0:
        return f"{value} 分钟（约 {value // 60} 小时）"
    return f"{value} 分钟（约 {round(value / 60.0, 1)} 小时）"


def format_hours(hours: float) -> str:
    try:
        value = float(hours)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"诊断小时数必须是有限数字：{hours!r}") from exc
    _ensure_finite_number(value, hours)
    if value == int(value):
        return f"{int(value)} 小时"
    return f"{round(value, 1)} 小时"


def graph_status_value(public: Dict[str, Any]) -> str:
    status = str(public.get("status") or "unknown")
    has_cycle = public.get("is_dag") is False or safe_int(public.get("cycle_edge_count")) > 0
    if status == "available" and has_cycle:
        return "发现循环关系"
    return GRAPH_STATUS_LABELS.get(status, "状态未知")


def error_count(selected_summary: Optional[Dict[str, Any]]) -> int:
    summary = safe_dict(selected_summary)
    explicit = summary.get("error_count")
    if explicit is not None:
        return safe_int(explicit)
    return len(safe_list(summary.get("errors")))


def summary_warning_count(selected_summary: Optional[Dict[str, Any]]) -> int:
    summary = safe_dict(selected_summary)
    explicit = summary.get("warning_count")
    if explicit is not None:
        return safe_int(explicit)
    return len(safe_list(summary.get("warnings")))


__all__ = [
    "NonFiniteDiagnosticNumber",
    "SAMPLE_LIMIT",
    "build_item",
    "build_section",
    "detail_from_samples",
    "error_count",
    "format_count",
    "format_hours",
    "format_minutes",
    "graph_diagnostics",
    "graph_public",
    "graph_status_value",
    "level_if",
    "safe_dict",
    "safe_float",
    "safe_int",
    "safe_list",
    "sample_text_values",
    "section_status_from_levels",
    "status_label",
    "summary_counts",
    "summary_warning_count",
    "text_if",
]
