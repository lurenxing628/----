from __future__ import annotations

from typing import Any, Dict, Optional

_FREEZE_STATE_LABELS = {
    "disabled": "未启用",
    "active": "已生效",
    "degraded": "部分未生效",
}


def _freeze_window_from_summary(selected_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    algo = selected_summary.get("algo") if selected_summary else None
    if not isinstance(algo, dict) or "freeze_window" not in algo:
        return None

    freeze_window = algo.get("freeze_window")
    if not isinstance(freeze_window, dict) or not freeze_window:
        return None
    return freeze_window


def _freeze_state(*, enabled: bool, applied: bool, raw_state: str, degraded: bool) -> str:
    if degraded:
        return "degraded"
    if raw_state in _FREEZE_STATE_LABELS:
        return raw_state
    if enabled and applied:
        return "active"
    return "disabled"


def build_freeze_display(selected_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    freeze_window = _freeze_window_from_summary(selected_summary)
    if freeze_window is None:
        return None

    enabled = str(freeze_window.get("enabled", "")).strip().lower() == "yes"
    applied = bool(freeze_window.get("freeze_applied"))
    raw_state = str(freeze_window.get("freeze_state") or "").strip().lower()
    sample_batches = list(freeze_window.get("frozen_batch_ids_sample") or [])[:5]
    sample_total = int(freeze_window.get("frozen_batch_count") or 0)
    degraded = bool(freeze_window.get("degraded")) or raw_state == "degraded"
    state = _freeze_state(
        enabled=enabled,
        applied=applied,
        raw_state=raw_state,
        degraded=degraded,
    )
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
