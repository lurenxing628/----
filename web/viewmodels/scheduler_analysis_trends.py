from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.models.scheduler_history_parser import parse_result_summary_payload

from .scheduler_analysis_overview import analysis_choice_label, build_analysis_labels
from .scheduler_history_summary import strategy_display_label


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or isinstance(v, bool) or (isinstance(v, str) and v.strip() == ""):
            return float(default)
        number = float(v)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    if not math.isfinite(number):
        return float(default)
    return number


def _metric_float_state(v: Any) -> Tuple[Optional[float], bool]:
    if isinstance(v, bool):
        return None, True
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None, False
    try:
        number = float(v)
    except (TypeError, ValueError, OverflowError):
        return None, True
    if not math.isfinite(number):
        return None, True
    return number, False


def _int_state(v: Any) -> Tuple[Optional[int], bool]:
    number, failed = _metric_float_state(v)
    if failed or number is None:
        return None, failed
    if not float(number).is_integer():
        return None, True
    return int(number), False


def _score_value(v: Any) -> float:
    try:
        if isinstance(v, bool):
            return float("inf")
        number = float(v)
    except (TypeError, ValueError, OverflowError):
        return float("inf")
    if not math.isfinite(number):
        return float("inf")
    return number


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or isinstance(v, bool) or (isinstance(v, str) and v.strip() == ""):
            return int(default)
        return int(float(v))
    except (TypeError, ValueError, OverflowError):
        return int(default)


def build_svg_polyline(values: List[Tuple[int, float]], *, width: int = 520, height: int = 120, pad: int = 18) -> Optional[Dict[str, Any]]:
    if not values:
        return None
    vals = [(int(x), float(y)) for x, y in values]
    if len(vals) < 2:
        return None

    ys = [y for _, y in vals]
    y_min = min(ys)
    y_max = max(ys)
    rng = (y_max - y_min) if (y_max - y_min) != 0 else 1.0

    xs = [x for x, _ in vals]
    x_min = min(xs)
    x_max = max(xs)
    x_rng = (x_max - x_min) if (x_max - x_min) != 0 else 1.0
    x_span = float(width - 2 * pad)
    y_span = float(height - 2 * pad)

    pts: List[Tuple[float, float]] = []
    for x0, y in vals:
        xx = float(pad) + ((float(x0) - float(x_min)) / float(x_rng)) * x_span
        yy = float(height - pad) - ((float(y) - float(y_min)) / rng) * y_span
        pts.append((xx, yy))

    points_str = " ".join([f"{round(x, 2)},{round(y, 2)}" for x, y in pts])
    last_xy = pts[-1]
    return {
        "width": int(width),
        "height": int(height),
        "pad": int(pad),
        "points": points_str,
        "y_min": float(y_min),
        "y_max": float(y_max),
        "last_x": float(last_xy[0]),
        "last_y": float(last_xy[1]),
        "x_labels": [x for x, _ in vals],
    }


def score_key(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, list) or not score:
        return (float("inf"),)
    return tuple(_score_value(x) for x in score)


def safe_load_json(value: Any) -> Dict[str, Any]:
    result = parse_result_summary_payload(value)
    return dict(result.payload) if isinstance(result.payload, dict) else {}


def metric_value(row: Dict[str, Any], key: str) -> Optional[float]:
    metrics = row.get("metrics") or {}
    if not isinstance(metrics, dict):
        return None
    value, failed = _metric_float_state(metrics.get(key))
    return None if failed else value


def _metric_has_parse_failure(metrics: Dict[str, Any], key: str) -> bool:
    _value, failed = _metric_float_state(metrics.get(key))
    return bool(failed)


def _metric_points(rows: List[Dict[str, Any]], key: str) -> List[Tuple[int, float]]:
    points: List[Tuple[int, float]] = []
    for row in rows or []:
        value = metric_value(row, key)
        if value is None:
            continue
        points.append((int(row["version"]), float(value)))
    return points


def _trend_history_dict(h: Any) -> Dict[str, Any]:
    return h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})


def _trend_row_state(
    d: Dict[str, Any],
    *,
    extract_metrics_from_summary,
) -> Optional[Tuple[int, Dict[str, Any]]]:
    ver, ver_parse_failed = _int_state(d.get("version"))
    if ver_parse_failed:
        return None
    ver = int(ver or 0)
    if ver <= 0:
        return None
    summary = safe_load_json(d.get("result_summary") or "")
    metrics = extract_metrics_from_summary(summary) or None
    if not metrics:
        return None
    algo = summary.get("algo") if isinstance(summary, dict) else None
    algo = algo if isinstance(algo, dict) else {}
    return ver, {
        "version": int(ver),
        "schedule_time": d.get("schedule_time"),
        "strategy": d.get("strategy"),
        "result_status": d.get("result_status"),
        "algo_mode": algo.get("mode"),
        "objective": algo.get("objective"),
        "metrics": metrics,
    }


def build_trend_rows(
    raw_hist: List[Any],
    *,
    extract_metrics_from_summary,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_ver: Dict[int, Dict[str, Any]] = {}
    for h in raw_hist or []:
        state = _trend_row_state(_trend_history_dict(h), extract_metrics_from_summary=extract_metrics_from_summary)
        if state is None:
            continue
        ver, row = state
        if ver in by_ver:
            continue
        by_ver[ver] = row

    trend_all = sorted(by_ver.values(), key=lambda x: int(x.get("version") or 0))
    trend_rows = trend_all[-30:] if len(trend_all) > 30 else trend_all
    return trend_all, trend_rows


def build_trend_charts(trend_rows: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "overdue": build_svg_polyline(_metric_points(trend_rows, "overdue_count")),
        "tardiness": build_svg_polyline(_metric_points(trend_rows, "total_tardiness_hours")),
        "weighted_tardiness": build_svg_polyline(_metric_points(trend_rows, "weighted_tardiness_hours")),
        "makespan": build_svg_polyline(_metric_points(trend_rows, "makespan_hours")),
        "makespan_internal": build_svg_polyline(_metric_points(trend_rows, "makespan_internal_hours")),
        "changeover": build_svg_polyline(_metric_points(trend_rows, "changeover_count")),
        "machine_util": build_svg_polyline(_metric_points(trend_rows, "machine_util_avg")),
        "operator_util": build_svg_polyline(_metric_points(trend_rows, "operator_util_avg")),
    }


def _selected_dict(selected_item: Any) -> Optional[Dict[str, Any]]:
    return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (selected_item if isinstance(selected_item, dict) else None)


def _selected_summary_context(selected: Dict[str, Any], *, extract_metrics_from_summary) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
    selected_summary = safe_load_json(selected.get("result_summary") or "")
    selected_metrics = extract_metrics_from_summary(selected_summary) if isinstance(selected_summary, dict) else None
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    return selected_summary, selected_metrics, (algo if isinstance(algo, dict) else {})


def _attempt_metric_state(attempt: Dict[str, Any], *, objective_key: str) -> Tuple[Dict[str, Any], Optional[float], bool]:
    raw_metrics = attempt.get("metrics")
    metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
    primary_value, primary_value_parse_failed = _metric_float_state(metrics.get(objective_key))
    return metrics, primary_value, primary_value_parse_failed


def _attempt_dispatch_labels(attempt: Dict[str, Any], labels: Dict[str, Dict[str, str]]) -> Tuple[Any, Any, str]:
    dispatch_mode = attempt.get("dispatch_mode") or ""
    dispatch_rule = attempt.get("dispatch_rule") or ""
    dispatch_mode_label = analysis_choice_label(dispatch_mode, labels.get("dispatch_mode", {}), empty_label="-")
    dispatch_rule_label = analysis_choice_label(dispatch_rule, labels.get("dispatch_rule", {}), empty_label="")
    dispatch_label = f"{dispatch_mode_label} / {dispatch_rule_label}" if dispatch_rule_label else dispatch_mode_label
    return dispatch_mode, dispatch_rule, dispatch_label


def _build_attempt_rows(algo: Dict[str, Any], *, objective_key: str) -> List[Dict[str, Any]]:
    attempts_rows: List[Dict[str, Any]] = []
    attempts = algo.get("attempts")
    if not isinstance(attempts, list):
        return attempts_rows
    labels = build_analysis_labels()
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        public_source_label = str(attempt.get("source_label") or "").strip()
        raw_tag = str(attempt.get("tag") or "").strip()
        source_tag = str(attempt.get("source") or attempt.get("origin") or "").strip()
        metrics, primary_value, primary_value_parse_failed = _attempt_metric_state(attempt, objective_key=objective_key)
        failed_ops, failed_ops_parse_failed = _int_state(attempt.get("failed_ops"))
        dispatch_mode, dispatch_rule, dispatch_label = _attempt_dispatch_labels(attempt, labels)
        attempts_rows.append(
            {
                "tag": raw_tag,
                "display_tag": public_source_label
                or _public_attempt_display_label(raw_tag=raw_tag, source_tag=source_tag),
                "strategy": attempt.get("strategy") or "-",
                "strategy_label": strategy_display_label(attempt.get("strategy")),
                "dispatch_mode": dispatch_mode,
                "dispatch_rule": dispatch_rule,
                "dispatch_label": dispatch_label,
                "failed_ops": failed_ops,
                "failed_ops_parse_failed": bool(failed_ops_parse_failed),
                "score": attempt.get("score") if isinstance(attempt.get("score"), list) else [],
                "metrics": metrics,
                "primary_value": primary_value,
                "primary_value_parse_failed": bool(primary_value_parse_failed),
            }
        )
    return attempts_rows


def _public_attempt_display_label(*, raw_tag: str, source_tag: str) -> str:
    for value in (source_tag, raw_tag):
        label = str(value or "").strip()
        if not label:
            continue
        known_label = _known_attempt_display_label(label)
        if known_label:
            return known_label
        if _is_public_attempt_label(label):
            return label
    return ""


def _known_attempt_display_label(label: str) -> str:
    if label == "baseline":
        return "原算法方案"
    if not label.startswith("graph_w") or "_of_" not in label:
        return ""
    parts = label.replace("graph_w", "", 1).split("_of_", 1)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return ""


def _is_public_attempt_label(label: str) -> bool:
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in label)
    has_ascii_letter = any(("a" <= ch.lower() <= "z") for ch in label)
    if any(token in label for token in ("|", ":", "/", "\\")):
        return False
    if "_" in label and not has_chinese:
        return False
    return not (has_ascii_letter and not has_chinese)


def _build_trace_chart(algo: Dict[str, Any], *, objective_key: str) -> Optional[Dict[str, Any]]:
    trace = algo.get("improvement_trace")
    if not isinstance(trace, list):
        return None
    trace_values: List[Tuple[int, float]] = []
    trace_metric_parse_failed = False
    trace_time_parse_failed = False
    for item in trace:
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        primary_value, primary_value_parse_failed = _metric_float_state(metrics.get(objective_key)) if isinstance(metrics, dict) else (None, False)
        if primary_value_parse_failed:
            trace_metric_parse_failed = True
            continue
        if primary_value is None:
            continue
        elapsed_ms, elapsed_ms_parse_failed = _int_state(item.get("elapsed_ms"))
        if elapsed_ms_parse_failed:
            trace_time_parse_failed = True
            continue
        if elapsed_ms is None:
            continue
        trace_values.append(
            (
                int(elapsed_ms),
                float(primary_value),
            )
        )
    if len(trace_values) < 2:
        return {"metric_parse_failed": True, "chart": None} if trace_metric_parse_failed or trace_time_parse_failed else None
    trace_values.sort(key=lambda x: x[0])
    chart = build_svg_polyline(trace_values, width=520, height=120, pad=18)
    if chart is not None:
        chart["metric_parse_failed"] = bool(trace_metric_parse_failed or trace_time_parse_failed)
    return chart


def _previous_metrics(trend_all: List[Dict[str, Any]], *, selected_ver: int) -> Optional[Dict[str, Any]]:
    for row in reversed(trend_all):
        if int(row.get("version") or 0) >= int(selected_ver):
            continue
        return row.get("metrics") if isinstance(row.get("metrics"), dict) else None
    return None


def build_selected_details(
    *,
    selected_ver: Optional[int],
    selected_item: Any,
    trend_all: List[Dict[str, Any]],
    extract_metrics_from_summary,
    comparison_metric_from_algo,
) -> Tuple[
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    str,
    List[Dict[str, Any]],
    Optional[Dict[str, Any]],
]:
    objective_key = "overdue_count"

    if selected_ver is None or not selected_item:
        return None, None, None, None, objective_key, [], None

    selected = _selected_dict(selected_item)
    if not selected:
        return None, None, None, None, objective_key, [], None

    selected_summary, selected_metrics, algo = _selected_summary_context(
        selected,
        extract_metrics_from_summary=extract_metrics_from_summary,
    )
    objective_key = comparison_metric_from_algo(algo)
    attempts_rows = _build_attempt_rows(algo, objective_key=objective_key)
    trace_chart = _build_trace_chart(algo, objective_key=objective_key)
    prev_metrics = _previous_metrics(trend_all, selected_ver=int(selected_ver))
    return selected, selected_summary, selected_metrics, prev_metrics, objective_key, attempts_rows, trace_chart


def sort_and_enrich_attempts(
    attempts_rows: List[Dict[str, Any]],
    *,
    selected_metrics: Optional[Dict[str, Any]],
    objective_key: str,
) -> List[Dict[str, Any]]:
    attempts_rows_sorted = sorted(attempts_rows or [], key=lambda r: score_key(r.get("score")))
    max_primary = 0.0
    if attempts_rows_sorted:
        max_primary = max([float(r["primary_value"]) for r in attempts_rows_sorted if r.get("primary_value") is not None] + [0.0])
    if selected_metrics and isinstance(selected_metrics, dict):
        selected_primary, selected_primary_failed = _metric_float_state(selected_metrics.get(objective_key))
        if selected_primary is not None and not selected_primary_failed:
            max_primary = max(max_primary, float(selected_primary))
    if max_primary <= 0:
        max_primary = 0.0
    for index, r in enumerate(attempts_rows_sorted, start=1):
        if not r.get("display_tag"):
            r["display_tag"] = f"方案 {index}"
        value = r.get("primary_value")
        if value is None or max_primary <= 0:
            r["bar_pct"] = None
        else:
            r["bar_pct"] = float(round((float(value) / max_primary) * 100.0, 4))
    return attempts_rows_sorted


__all__ = [
    "_metric_float_state",
    "_metric_has_parse_failure",
    "build_selected_details",
    "build_svg_polyline",
    "build_trend_charts",
    "build_trend_rows",
    "metric_value",
    "safe_float",
    "safe_int",
    "score_key",
    "sort_and_enrich_attempts",
]
