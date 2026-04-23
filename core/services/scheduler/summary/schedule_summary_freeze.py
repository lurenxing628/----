from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import YesNo
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot


def _freeze_window_config_state(cfg: Any) -> Tuple[bool, int]:
    snapshot = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.freeze_window",
    )
    enabled = str(snapshot.freeze_window_enabled).strip().lower() == YesNo.YES.value
    return bool(enabled), int(snapshot.freeze_window_days)


def _freeze_degradation_codes(meta: Dict[str, Any]) -> List[str]:
    return [str(code).strip() for code in list(meta.get("freeze_degradation_codes") or []) if str(code).strip()]


def _freeze_applied(meta: Dict[str, Any], *, frozen_op_ids: Set[int]) -> bool:
    if "freeze_applied" in meta:
        return bool(meta.get("freeze_applied"))
    return bool(frozen_op_ids)


def _freeze_state_name(*, enabled: bool, days: int, applied: bool, degraded: bool) -> str:
    if degraded:
        return "degraded"
    if enabled and days > 0 and applied:
        return "active"
    return "disabled"


def _compute_result_status(summary: Any, *, simulate: bool) -> str:
    if getattr(summary, "success", False):
        result_status = "success"
    elif int(getattr(summary, "scheduled_ops", 0) or 0) > 0:
        result_status = "partial"
    else:
        result_status = "failed"
    if simulate:
        result_status = "simulated"
    return result_status


def _frozen_batch_ids(operations: List[Any], *, frozen_op_ids: Set[int]) -> List[str]:
    return sorted(
        {
            str(op.batch_id or "")
            for op in operations
            if op and getattr(op, "id", None) and int(op.id) in frozen_op_ids and str(op.batch_id or "").strip()
        }
    )


def _extract_freeze_warnings(all_warnings: Any) -> List[str]:
    warnings_list = all_warnings if isinstance(all_warnings, list) else list(all_warnings or [])
    freeze_warnings: List[str] = []
    for warning in warnings_list:
        text = str(warning)
        if text.startswith("[freeze_window]") or text.startswith("【冻结窗口】"):
            freeze_warnings.append(text)
            continue
        if text.startswith("【冻结窗口】"):
            freeze_warnings.append(text)
    return freeze_warnings


def _freeze_meta_dict(
    cfg: Any,
    *,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
    freeze_warnings: List[str],
) -> Dict[str, Any]:
    meta = freeze_meta if isinstance(freeze_meta, dict) else {}
    enabled, days = _freeze_window_config_state(cfg)
    raw_state = str(meta.get("freeze_state") or "").strip().lower()
    degradation_codes = _freeze_degradation_codes(meta)
    has_freeze_meta = bool(meta)
    degraded = raw_state == "degraded" or bool(degradation_codes) or (not has_freeze_meta and bool(freeze_warnings))
    applied = _freeze_applied(meta, frozen_op_ids=frozen_op_ids)
    freeze_state = _freeze_state_name(enabled=enabled, days=days, applied=applied, degraded=degraded)
    return {
        "enabled": bool(enabled),
        "days": int(days),
        "freeze_state": freeze_state,
        "freeze_applied": bool(applied),
        "freeze_degradation_codes": degradation_codes,
        "degradation_from_warning_fallback": bool(not has_freeze_meta and bool(freeze_warnings)),
        "degradation_reason": meta.get("freeze_degradation_reason") or (freeze_warnings[0] if (not has_freeze_meta and freeze_warnings) else None),
    }
