from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_analysis_labels import objective_label_for

_COMPAT_FALLBACK_FIELD_LABELS = {
    "comparison_metric": "优化对比指标",
    "best_score_schema": "评分顺序",
}


def _best_score_schema_display(selected_summary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    if not isinstance(algo, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for raw_item in algo.get("best_score_schema") or []:
        if not isinstance(raw_item, dict):
            continue
        row = dict(raw_item)
        row["display_label"] = str(row.get("label") or "").strip() or objective_label_for(row.get("key"), algo=algo)
        rows.append(row)
    return rows


def _compat_fallback_state(selected_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    if not isinstance(algo, dict):
        return {"used": False, "missing_fields": [], "message": None}

    missing_fields: List[str] = []
    if not str(algo.get("comparison_metric") or "").strip():
        missing_fields.append("comparison_metric")
    if not isinstance(algo.get("best_score_schema"), list):
        missing_fields.append("best_score_schema")
    if not missing_fields:
        return {"used": False, "missing_fields": [], "missing_field_labels": [], "message": None}
    return {
        "used": True,
        "missing_fields": missing_fields,
        "missing_field_labels": [_COMPAT_FALLBACK_FIELD_LABELS.get(field, "分析字段") for field in missing_fields],
        "message": "这个历史版本缺少新的分析字段，页面只展示能确认的内容。",
    }


__all__ = [
    "_best_score_schema_display",
    "_compat_fallback_state",
]
