from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or str(v).strip() == "":
            return int(default)
        return int(float(v))
    except Exception:
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
    out: List[float] = []
    for x in score:
        try:
            out.append(float(x))
        except Exception:
            out.append(float("inf"))
    return tuple(out)


def safe_load_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    s = str(value).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def metric_value(row: Dict[str, Any], key: str) -> float:
    metrics = row.get("metrics") or {}
    if not isinstance(metrics, dict):
        return 0.0
    return safe_float(metrics.get(key), default=0.0)


def build_trend_rows(
    raw_hist: List[Any],
    *,
    extract_metrics_from_summary,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_ver: Dict[int, Dict[str, Any]] = {}
    for h in raw_hist or []:
        try:
            d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})
        except Exception:
            d = {}
        ver = safe_int(d.get("version"), default=0)
        if ver <= 0 or ver in by_ver:
            continue
        summary = safe_load_json(d.get("result_summary") or "")
        metrics = extract_metrics_from_summary(summary) or None
        if not metrics:
            continue
        algo = summary.get("algo") if isinstance(summary, dict) else None
        algo = algo if isinstance(algo, dict) else {}
        by_ver[int(ver)] = {
            "version": int(ver),
            "schedule_time": d.get("schedule_time"),
            "strategy": d.get("strategy"),
            "result_status": d.get("result_status"),
            "algo_mode": algo.get("mode"),
            "objective": algo.get("objective"),
            "metrics": metrics,
        }

    trend_all = sorted(by_ver.values(), key=lambda x: int(x.get("version") or 0))
    trend_rows = trend_all[-30:] if len(trend_all) > 30 else trend_all
    return trend_all, trend_rows


def build_trend_charts(trend_rows: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "overdue": build_svg_polyline([(r["version"], metric_value(r, "overdue_count")) for r in trend_rows]),
        "tardiness": build_svg_polyline([(r["version"], metric_value(r, "total_tardiness_hours")) for r in trend_rows]),
        "weighted_tardiness": build_svg_polyline(
            [(r["version"], metric_value(r, "weighted_tardiness_hours")) for r in trend_rows]
        ),
        "makespan": build_svg_polyline([(r["version"], metric_value(r, "makespan_hours")) for r in trend_rows]),
        "makespan_internal": build_svg_polyline(
            [(r["version"], metric_value(r, "makespan_internal_hours")) for r in trend_rows]
        ),
        "changeover": build_svg_polyline([(r["version"], metric_value(r, "changeover_count")) for r in trend_rows]),
        "machine_util": build_svg_polyline([(r["version"], metric_value(r, "machine_util_avg")) for r in trend_rows]),
        "operator_util": build_svg_polyline([(r["version"], metric_value(r, "operator_util_avg")) for r in trend_rows]),
    }


def _selected_dict(selected_item: Any) -> Optional[Dict[str, Any]]:
    try:
        return selected_item.to_dict() if hasattr(selected_item, "to_dict") else (selected_item if isinstance(selected_item, dict) else None)
    except Exception:
        return None


def _selected_summary_context(selected: Dict[str, Any], *, extract_metrics_from_summary) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
    selected_summary = safe_load_json(selected.get("result_summary") or "")
    selected_metrics = extract_metrics_from_summary(selected_summary) if isinstance(selected_summary, dict) else None
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    return selected_summary, selected_metrics, (algo if isinstance(algo, dict) else {})


def _build_attempt_rows(algo: Dict[str, Any], *, objective_key: str) -> List[Dict[str, Any]]:
    attempts_rows: List[Dict[str, Any]] = []
    attempts = algo.get("attempts")
    if not isinstance(attempts, list):
        return attempts_rows
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        metrics = attempt.get("metrics") if isinstance(attempt.get("metrics"), dict) else {}
        raw_tag = str(attempt.get("tag") or "").strip()
        source_tag = str(attempt.get("source") or attempt.get("origin") or "").strip()
        attempts_rows.append(
            {
                "tag": raw_tag,
                "display_tag": _public_attempt_display_label(raw_tag=raw_tag, source_tag=source_tag),
                "strategy": attempt.get("strategy") or "-",
                "dispatch_mode": attempt.get("dispatch_mode") or "",
                "dispatch_rule": attempt.get("dispatch_rule") or "",
                "failed_ops": safe_int(attempt.get("failed_ops"), default=0),
                "score": attempt.get("score") if isinstance(attempt.get("score"), list) else [],
                "metrics": metrics,
                "primary_value": safe_float(metrics.get(objective_key), default=0.0) if isinstance(metrics, dict) else 0.0,
            }
        )
    return attempts_rows


def _public_attempt_display_label(*, raw_tag: str, source_tag: str) -> str:
    for value in (source_tag, raw_tag):
        label = str(value or "").strip()
        if not label:
            continue
        if "|" in label or ":" in label or "/" in label or "\\" in label:
            continue
        if "_" in label and not any("\u4e00" <= ch <= "\u9fff" for ch in label):
            continue
        return label
    return ""


def _build_trace_chart(algo: Dict[str, Any], *, objective_key: str) -> Optional[Dict[str, Any]]:
    trace = algo.get("improvement_trace")
    if not isinstance(trace, list):
        return None
    trace_values: List[Tuple[int, float]] = []
    for item in trace:
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        trace_values.append(
            (
                int(safe_int(item.get("elapsed_ms"), default=0)),
                float(safe_float(metrics.get(objective_key), default=0.0) if isinstance(metrics, dict) else 0.0),
            )
        )
    if len(trace_values) < 2:
        return None
    trace_values.sort(key=lambda x: x[0])
    return build_svg_polyline(trace_values, width=520, height=120, pad=18)


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
        max_primary = max([safe_float(r.get("primary_value"), default=0.0) for r in attempts_rows_sorted] + [0.0])
    if selected_metrics and isinstance(selected_metrics, dict):
        max_primary = max(max_primary, safe_float(selected_metrics.get(objective_key), default=0.0))
    if max_primary <= 0:
        max_primary = 0.0
    for index, r in enumerate(attempts_rows_sorted, start=1):
        if not r.get("display_tag"):
            r["display_tag"] = f"方案 {index}"
        v = safe_float(r.get("primary_value"), default=0.0)
        r["bar_pct"] = 0.0 if max_primary <= 0 else float(round((v / max_primary) * 100.0, 4))
    return attempts_rows_sorted
