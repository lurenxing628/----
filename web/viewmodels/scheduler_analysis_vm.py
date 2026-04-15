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


def extract_metrics_from_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    algo = summary.get("algo") if isinstance(summary, dict) else None
    if isinstance(algo, dict):
        m = algo.get("metrics")
        if isinstance(m, dict) and m:
            return m
    return None


_EXTRA_CARD_SPECS = (
    ("invalid_due_count", "数据异常批次数", "type-info"),
    ("unscheduled_batch_count", "未排批次数", ""),
)

_FREEZE_STATE_LABELS = {
    "disabled": "未启用",
    "active": "已生效",
    "degraded": "已降级",
}

_SUMMARY_DEGRADATION_LABELS = {
    "freeze_window_degraded": "冻结窗口约束已降级",
    "downtime_avoid_degraded": "停机避让约束已降级",
    "resource_pool_degraded": "资源池构建已降级",
    "invalid_due_date": "交期数据已降级",
    "legacy_external_days_defaulted": "历史外协周期已兼容回退",
    "ortools_warmstart_failed": "预热已降级",
    "template_missing": "组合并模板上下文已降级",
    "external_group_missing": "组合并外部组上下文已降级",
}


def _summary_metric_value(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    key: str,
) -> Optional[Any]:
    if selected_metrics and key in selected_metrics:
        return selected_metrics[key]
    if selected_summary and key in selected_summary:
        return selected_summary[key]
    return None


def build_extra_cards(
    selected_summary: Optional[Dict[str, Any]],
    selected_metrics: Optional[Dict[str, Any]],
    prev_metrics: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for key, label, type_class in _EXTRA_CARD_SPECS:
        value = _summary_metric_value(selected_summary, selected_metrics, key)
        if value is None:
            continue
        delta = int(value) - int(prev_metrics[key]) if prev_metrics and key in prev_metrics else None
        cards.append(
            {
                "key": key,
                "label": label,
                "value": int(value),
                "delta": delta,
                "type_class": type_class,
            }
        )
    return cards


def build_freeze_display(selected_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    algo = selected_summary.get("algo") if selected_summary else None
    if not algo or "freeze_window" not in algo:
        return None

    freeze_window = algo.get("freeze_window")
    if not freeze_window:
        return None

    enabled = str(freeze_window.get("enabled", "")).strip().lower() == "yes"
    applied = bool(freeze_window.get("freeze_applied"))
    raw_state = str(freeze_window.get("freeze_state") or "").strip().lower()
    sample_batches = list(freeze_window.get("frozen_batch_ids_sample") or [])[:5]
    sample_total = int(freeze_window.get("frozen_batch_count") or 0)
    degraded = bool(freeze_window.get("degraded")) or raw_state == "degraded"
    if degraded:
        state = "degraded"
    elif raw_state in _FREEZE_STATE_LABELS:
        state = raw_state
    elif enabled and applied:
        state = "active"
    else:
        state = "disabled"
    return {
        "enabled": enabled,
        "days": int(freeze_window.get("days") or 0),
        "state": state,
        "state_label": _FREEZE_STATE_LABELS[state],
        "applied": applied,
        "frozen_op_count": int(freeze_window.get("frozen_op_count") or 0),
        "frozen_batch_count": sample_total,
        "sample_batches": sample_batches,
        "sample_total": sample_total,
        "sample_more_count": max(sample_total - len(sample_batches), 0),
        "degraded": degraded,
        "degradation_reason": freeze_window.get("degradation_reason") or None,
    }


def build_summary_degradation_messages(selected_summary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(selected_summary, dict):
        return []

    events = selected_summary.get("degradation_events")
    if not isinstance(events, list):
        return []

    items: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        code = str(event.get("code") or "").strip()
        message = str(event.get("message") or "").strip()
        if not code and not message:
            continue
        dedupe_key = (code, message)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(
            {
                "code": code,
                "label": _SUMMARY_DEGRADATION_LABELS.get(code) or "排产摘要存在可见退化",
                "message": message,
                "count": max(1, safe_int(event.get("count"), default=1)),
            }
        )
    return items


def build_svg_polyline(values: List[Tuple[int, float]], *, width: int = 520, height: int = 120, pad: int = 18) -> Optional[Dict[str, Any]]:
    """
    把 (x_label, y) 序列转为简单折线图（SVG polyline）。
    - 不依赖任何外部 JS/库，适合 Win7 离线环境。
    """
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
        # y 越大越靠上：反向映射到画布坐标
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
    """
    attempts 的 score 排序 key（越小越好）。
    - score 为空/不合法时视为 +inf（排到最后）
    """
    if not isinstance(score, list) or not score:
        return (float("inf"),)
    out: List[float] = []
    for x in score:
        try:
            out.append(float(x))
        except Exception:
            out.append(float("inf"))
    return tuple(out)


def _safe_load_json(value: Any) -> Dict[str, Any]:
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


def _objective_key_from_algo_objective(obj: Any) -> str:
    v = str(obj or "min_overdue").strip().lower()
    if v == "min_tardiness":
        return "total_tardiness_hours"
    if v == "min_weighted_tardiness":
        return "weighted_tardiness_hours"
    if v == "min_changeover":
        return "changeover_count"
    return "overdue_count"


def _comparison_metric_from_algo(algo: Any) -> str:
    if isinstance(algo, dict):
        metric = str(algo.get("comparison_metric") or "").strip()
        if metric:
            return metric
        schema = algo.get("best_score_schema")
        if isinstance(schema, list):
            for item in schema:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                if key and key != "failed_ops":
                    return key
    obj = algo.get("objective") if isinstance(algo, dict) else None
    return _objective_key_from_algo_objective(obj)


def _metric_value(row: Dict[str, Any], key: str) -> float:
    m = row.get("metrics") or {}
    if not isinstance(m, dict):
        return 0.0
    return safe_float(m.get(key), default=0.0)


def build_trend_rows(raw_hist: List[Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    从 history 列表抽取最近版本趋势（去重 version，且要求 summary.algo.metrics 存在）。
    返回：
    - trend_all：按 version 升序的完整趋势行
    - trend_rows：截断到最后 30 条的趋势行
    """
    by_ver: Dict[int, Dict[str, Any]] = {}
    for h in raw_hist or []:
        try:
            d = h.to_dict() if hasattr(h, "to_dict") else (h if isinstance(h, dict) else {})
        except Exception:
            d = {}
        ver = safe_int(d.get("version"), default=0)
        if ver <= 0 or ver in by_ver:
            continue
        summary = _safe_load_json(d.get("result_summary") or "")
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
        "overdue": build_svg_polyline([(r["version"], _metric_value(r, "overdue_count")) for r in trend_rows]),
        "tardiness": build_svg_polyline([(r["version"], _metric_value(r, "total_tardiness_hours")) for r in trend_rows]),
        "weighted_tardiness": build_svg_polyline(
            [(r["version"], _metric_value(r, "weighted_tardiness_hours")) for r in trend_rows]
        ),
        "makespan": build_svg_polyline([(r["version"], _metric_value(r, "makespan_hours")) for r in trend_rows]),
        "makespan_internal": build_svg_polyline(
            [(r["version"], _metric_value(r, "makespan_internal_hours")) for r in trend_rows]
        ),
        "changeover": build_svg_polyline([(r["version"], _metric_value(r, "changeover_count")) for r in trend_rows]),
        "machine_util": build_svg_polyline([(r["version"], _metric_value(r, "machine_util_avg")) for r in trend_rows]),
        "operator_util": build_svg_polyline([(r["version"], _metric_value(r, "operator_util_avg")) for r in trend_rows]),
    }


def build_selected_details(
    *,
    selected_ver: Optional[int],
    selected_item: Any,
    trend_all: List[Dict[str, Any]],
) -> Tuple[
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    str,
    List[Dict[str, Any]],
    Optional[Dict[str, Any]],
]:
    selected: Optional[Dict[str, Any]] = None
    selected_summary: Optional[Dict[str, Any]] = None
    selected_metrics: Optional[Dict[str, Any]] = None
    prev_metrics: Optional[Dict[str, Any]] = None
    attempts_rows: List[Dict[str, Any]] = []
    trace_chart: Optional[Dict[str, Any]] = None
    objective_key = "overdue_count"

    if selected_ver is None or not selected_item:
        return selected, selected_summary, selected_metrics, prev_metrics, objective_key, attempts_rows, trace_chart

    try:
        selected = selected_item.to_dict() if hasattr(selected_item, "to_dict") else (selected_item if isinstance(selected_item, dict) else None)
    except Exception:
        selected = None
    if not selected:
        return None, None, None, None, objective_key, [], None

    selected_summary = _safe_load_json(selected.get("result_summary") or "")
    selected_metrics = extract_metrics_from_summary(selected_summary) if isinstance(selected_summary, dict) else None

    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    algo = algo if isinstance(algo, dict) else {}
    objective_key = _comparison_metric_from_algo(algo)

    attempts = algo.get("attempts") if isinstance(algo, dict) else None
    if isinstance(attempts, list):
        for a in attempts:
            if not isinstance(a, dict):
                continue
            m = a.get("metrics") if isinstance(a.get("metrics"), dict) else {}
            score = a.get("score") if isinstance(a.get("score"), list) else []
            attempts_rows.append(
                {
                    "tag": a.get("tag") or "-",
                    "strategy": a.get("strategy") or "-",
                    "dispatch_mode": a.get("dispatch_mode") or "-",
                    "dispatch_rule": a.get("dispatch_rule") or "-",
                    "failed_ops": safe_int(a.get("failed_ops"), default=0),
                    "score": score,
                    "metrics": m,
                    "primary_value": safe_float(m.get(objective_key), default=0.0) if isinstance(m, dict) else 0.0,
                }
            )

    trace = algo.get("improvement_trace") if isinstance(algo, dict) else None
    trace_values: List[Tuple[int, float]] = []
    if isinstance(trace, list):
        for t in trace:
            if not isinstance(t, dict):
                continue
            ms = safe_int(t.get("elapsed_ms"), default=0)
            mm = t.get("metrics") if isinstance(t.get("metrics"), dict) else {}
            pv = safe_float(mm.get(objective_key), default=0.0) if isinstance(mm, dict) else 0.0
            trace_values.append((int(ms), float(pv)))
    if len(trace_values) >= 2:
        trace_values.sort(key=lambda x: x[0])
        trace_chart = build_svg_polyline(trace_values, width=520, height=120, pad=18)

    if trend_all:
        prev = None
        for r in reversed(trend_all):
            if int(r.get("version") or 0) < int(selected_ver):
                prev = r
                break
        if prev and isinstance(prev.get("metrics"), dict):
            prev_metrics = prev.get("metrics")

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
    for r in attempts_rows_sorted:
        v = safe_float(r.get("primary_value"), default=0.0)
        r["bar_pct"] = 0.0 if max_primary <= 0 else float(round((v / max_primary) * 100.0, 4))
    return attempts_rows_sorted


def build_analysis_context(
    *,
    selected_ver: Optional[int],
    raw_hist: List[Any],
    selected_item: Any,
) -> Dict[str, Any]:
    trend_all, trend_rows = build_trend_rows(raw_hist)
    trend_charts = build_trend_charts(trend_rows)
    (
        selected,
        selected_summary,
        selected_metrics,
        prev_metrics,
        objective_key,
        attempts_rows,
        trace_chart,
    ) = build_selected_details(selected_ver=selected_ver, selected_item=selected_item, trend_all=trend_all)
    extra_cards = build_extra_cards(selected_summary, selected_metrics, prev_metrics)
    freeze_display = build_freeze_display(selected_summary)
    summary_degradation_messages = build_summary_degradation_messages(selected_summary)
    attempts = sort_and_enrich_attempts(attempts_rows, selected_metrics=selected_metrics, objective_key=objective_key)
    return {
        "selected": selected,
        "selected_summary": selected_summary,
        "selected_metrics": selected_metrics,
        "prev_metrics": prev_metrics,
        "objective_key": objective_key,
        "attempts": attempts,
        "trace_chart": trace_chart,
        "trend_rows": trend_rows,
        "trend_charts": trend_charts,
        "extra_cards": extra_cards,
        "freeze_display": freeze_display,
        "summary_degradation_messages": summary_degradation_messages,
    }

