from __future__ import annotations

from typing import Any, Dict, Optional

_FREEZE_STATE_LABELS = {
    "disabled": "未启用",
    "active": "已生效",
    "degraded": "部分未生效",
}


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


__all__ = ["build_freeze_display"]
