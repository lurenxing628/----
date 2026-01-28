from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from flask import g, request

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from data.repositories import ScheduleHistoryRepository
from web.viewmodels.scheduler_analysis_vm import (
    build_svg_polyline,
    extract_metrics_from_summary,
    safe_float,
    safe_int,
    score_key,
)

from .scheduler_bp import bp

@bp.get("/analysis")
def analysis_page():
    """
    排产效果/优化分析：
    - 展示 result_summary.algo 中的指标、尝试列表（attempts），以及最近版本趋势。
    - 不依赖外网与第三方图表库（Win7 离线可用）。
    """
    repo = ScheduleHistoryRepository(g.db)
    versions = repo.list_versions(limit=50)

    ver_raw = (request.args.get("version") or "").strip()
    selected_ver: Optional[int] = None
    if ver_raw:
        try:
            selected_ver = int(ver_raw)
        except Exception:
            raise ValidationError("version 不合法（期望整数）", field="version")
    else:
        if versions:
            try:
                selected_ver = int(versions[0]["version"])
            except Exception:
                selected_ver = None

    # 趋势：取最近若干条 history（去重 version），抽取 algo.metrics
    raw_hist = repo.list_recent(limit=400)
    by_ver: Dict[int, Dict[str, Any]] = {}
    for h in raw_hist:
        d = h.to_dict()
        ver = safe_int(d.get("version"), default=0)
        if ver <= 0 or ver in by_ver:
            continue
        rs = d.get("result_summary") or ""
        try:
            summary = json.loads(rs) if rs else {}
        except Exception:
            summary = {}
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

    def _mval(row: Dict[str, Any], key: str) -> float:
        m = row.get("metrics") or {}
        if not isinstance(m, dict):
            return 0.0
        return safe_float(m.get(key), default=0.0)

    trend_charts = {
        "overdue": build_svg_polyline([(r["version"], _mval(r, "overdue_count")) for r in trend_rows]),
        "tardiness": build_svg_polyline([(r["version"], _mval(r, "total_tardiness_hours")) for r in trend_rows]),
        "weighted_tardiness": build_svg_polyline([(r["version"], _mval(r, "weighted_tardiness_hours")) for r in trend_rows]),
        "makespan": build_svg_polyline([(r["version"], _mval(r, "makespan_hours")) for r in trend_rows]),
        "makespan_internal": build_svg_polyline([(r["version"], _mval(r, "makespan_internal_hours")) for r in trend_rows]),
        "changeover": build_svg_polyline([(r["version"], _mval(r, "changeover_count")) for r in trend_rows]),
        "machine_util": build_svg_polyline([(r["version"], _mval(r, "machine_util_avg")) for r in trend_rows]),
        "operator_util": build_svg_polyline([(r["version"], _mval(r, "operator_util_avg")) for r in trend_rows]),
    }

    selected = None
    selected_summary = None
    selected_metrics = None
    prev_metrics = None
    attempts_rows: List[Dict[str, Any]] = []
    objective_key = "overdue_count"
    trace_chart = None
    if selected_ver is not None:
        item = repo.get_by_version(int(selected_ver))
        if item:
            selected = item.to_dict()
            rs = selected.get("result_summary") or ""
            try:
                selected_summary = json.loads(rs) if rs else {}
            except Exception:
                selected_summary = None
            if isinstance(selected_summary, dict):
                selected_metrics = extract_metrics_from_summary(selected_summary)
                algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
                algo = algo if isinstance(algo, dict) else {}
                obj = str(algo.get("objective") or "min_overdue").strip()
                if obj == "min_tardiness":
                    objective_key = "total_tardiness_hours"
                elif obj == "min_changeover":
                    objective_key = "changeover_count"
                else:
                    objective_key = "overdue_count"

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
                                "failed_ops": safe_int(a.get("failed_ops"), default=0),
                                "score": score,
                                "metrics": m,
                                "primary_value": safe_float(m.get(objective_key), default=0.0) if isinstance(m, dict) else 0.0,
                            }
                        )

                # 改进轨迹：仅记录“找到更优解”的点（按 elapsed_ms 展示）
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

                # 前一版本（有指标的最近一个版本）
                if trend_all:
                    prev = None
                    for r in reversed(trend_all):
                        if int(r.get("version") or 0) < int(selected_ver):
                            prev = r
                            break
                    if prev and isinstance(prev.get("metrics"), dict):
                        prev_metrics = prev.get("metrics")

    # attempts：按 score 字典序排序（越小越好），并计算条形宽度（值越大条越长）
    attempts_rows_sorted = sorted(attempts_rows, key=lambda r: score_key(r.get("score")))
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

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=versions,
        selected=selected,
        selected_summary=selected_summary,
        selected_metrics=selected_metrics,
        prev_metrics=prev_metrics,
        objective_key=objective_key,
        attempts=attempts_rows_sorted,
        trace_chart=trace_chart,
        trend_rows=trend_rows,
        trend_charts=trend_charts,
    )

