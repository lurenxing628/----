from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .scheduler_analysis_trends import safe_float as _trend_safe_float

MetricNumber = Tuple[Optional[float], bool]
MetricInt = Tuple[Optional[int], bool]
_MISSING = object()


def safe_float(v: Any, default: float = 0.0) -> float:
    return _trend_safe_float(v, default=default)


def _number_state(value: Any) -> MetricNumber:
    if isinstance(value, bool):
        return None, True
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None, False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None, True
    if not math.isfinite(number):
        return None, True
    return number, False


def _int_state(value: Any) -> MetricInt:
    number, failed = _number_state(value)
    if failed or number is None:
        return None, failed
    if not float(number).is_integer():
        return None, True
    return int(number), False


def _required_number_state(value: Any) -> MetricNumber:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None, True
    return _number_state(value)


def _required_int_state(value: Any) -> MetricInt:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None, True
    return _int_state(value)


def _metric_number_text(value: Optional[float], *, failed: bool, percent: bool = False) -> str:
    if failed:
        return "无法安全展示"
    number = float(value or 0.0)
    if percent:
        return f"{round(number * 100, 2)}%"
    return str(round(number, 4))


def _metric_int_text(value: Optional[int], *, failed: bool) -> str:
    if failed:
        return "无法安全展示"
    return str(int(value or 0))


def _present(metrics: Dict[str, Any], key: str) -> bool:
    if key not in metrics:
        return False
    value = metrics.get(key)
    return not (value is None or (isinstance(value, str) and value.strip() == ""))


def _delta_text(current: Optional[float], previous: Any, *, integer: bool = False) -> str:
    previous_value, previous_failed = (_int_state(previous) if integer else _number_state(previous))
    if current is None or previous_value is None or previous_failed:
        return ""
    delta = float(current) - float(previous_value)
    if integer:
        delta_value = int(delta)
        return f"对比上一版：{'+' if delta_value > 0 else ''}{delta_value}"
    delta_value = round(delta, 4)
    return f"对比上一版：{'+' if delta_value > 0 else ''}{delta_value}"


def _used_count_text(metrics: Dict[str, Any], key: str, unit: str) -> str:
    if not _present(metrics, key):
        return f"已用 无法安全展示 {unit}"
    value, failed = _required_int_state(metrics.get(key))
    return f"已用 {_metric_int_text(value, failed=failed)} {unit}"


def _load_cv_text(metrics: Dict[str, Any], key: str) -> str:
    if not _present(metrics, key):
        return "任务分配均匀程度 无法安全展示，越小越均匀"
    value, failed = _required_number_state(metrics.get(key))
    return f"任务分配均匀程度 {_metric_number_text(value, failed=failed)}，越小越均匀"


def extract_metrics_from_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    algo = summary.get("algo") if isinstance(summary, dict) else None
    if isinstance(algo, dict):
        metrics = algo.get("metrics")
        if isinstance(metrics, dict) and metrics:
            return metrics
    return None


_EXTRA_CARD_SPECS = (
    ("invalid_due_count", "数据异常批次数", "type-info"),
    ("unscheduled_batch_count", "未排批次数", ""),
)

_METRIC_CARD_SPECS = (
    ("overdue_count", "超期批次数", "type-danger", "danger", "int"),
    ("total_tardiness_hours", "总拖期（小时）", "", "", "float"),
    ("weighted_tardiness_hours", "加权拖期（小时）", "", "", "float"),
    ("makespan_hours", "总工期（小时）", "", "", "float"),
    ("makespan_internal_hours", "内制工期（小时）", "", "", "float"),
    ("changeover_count", "换型次数", "", "", "int"),
)


def _summary_metric_value(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    key: str,
) -> Any:
    if selected_metrics and key in selected_metrics:
        return selected_metrics[key]
    if selected_summary and key in selected_summary:
        return selected_summary[key]
    return _MISSING


def build_extra_cards(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    prev_metrics: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for key, label, type_class in _EXTRA_CARD_SPECS:
        raw_value = _summary_metric_value(selected_summary, selected_metrics, key)
        if raw_value is _MISSING:
            continue
        value, failed = _required_int_state(raw_value)
        prev_value, prev_failed = _int_state(prev_metrics.get(key)) if prev_metrics and key in prev_metrics else (None, False)
        display_value: Any = "无法安全展示"
        if not failed and value is not None:
            display_value = int(value)
        cards.append(
            {
                "key": key,
                "label": label,
                "value": display_value,
                "delta": (int(value) - int(prev_value)) if value is not None and prev_value is not None and not prev_failed else None,
                "type_class": "type-danger" if failed else type_class,
            }
        )
    return cards


def build_metric_cards(
    selected_metrics: Optional[Dict[str, Any]],
    prev_metrics: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metrics = selected_metrics if isinstance(selected_metrics, dict) else None
    if not metrics:
        return []

    cards: List[Dict[str, Any]] = []
    for key, label, type_class, value_class, kind in _METRIC_CARD_SPECS:
        raw_value = metrics.get(key)
        if kind == "int":
            value, failed = _required_int_state(raw_value)
            value_text = _metric_int_text(value, failed=failed)
            delta = "" if failed else _delta_text(float(value or 0), (prev_metrics or {}).get(key), integer=True)
        else:
            value, failed = _required_number_state(raw_value)
            value_text = _metric_number_text(value, failed=failed)
            delta = "" if failed else _delta_text(value or 0.0, (prev_metrics or {}).get(key), integer=False)
        cards.append(
            {
                "key": key,
                "label": label,
                "value": value_text,
                "value_class": value_class,
                "delta": delta,
                "secondary": [],
                "type_class": "type-danger" if failed else type_class,
            }
        )

    machine_util, machine_failed = _required_number_state(metrics.get("machine_util_avg"))
    cards.append(
        {
            "key": "machine_util_avg",
            "label": "设备平均利用率",
            "value": _metric_number_text(machine_util, failed=machine_failed, percent=True),
            "value_class": "primary",
            "delta": "",
            "secondary": [
                _used_count_text(metrics, "machine_used_count", "台"),
                _load_cv_text(metrics, "machine_load_cv"),
            ],
            "type_class": "type-danger" if machine_failed else "type-primary",
        }
    )

    operator_util, operator_failed = _required_number_state(metrics.get("operator_util_avg"))
    cards.append(
        {
            "key": "operator_util_avg",
            "label": "人员平均利用率",
            "value": _metric_number_text(operator_util, failed=operator_failed, percent=True),
            "value_class": "success",
            "delta": "",
            "secondary": [
                _used_count_text(metrics, "operator_used_count", "人"),
                _load_cv_text(metrics, "operator_load_cv"),
            ],
            "type_class": "type-danger" if operator_failed else "type-success",
        }
    )
    return cards


__all__ = [
    "build_extra_cards",
    "build_metric_cards",
    "extract_metrics_from_summary",
    "safe_float",
]
