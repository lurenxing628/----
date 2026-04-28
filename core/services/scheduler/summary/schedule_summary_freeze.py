from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models.enums import YesNo
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.degradation_messages import (
    FREEZE_WINDOW_DEGRADED_MESSAGE,
    FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
)
from core.services.scheduler.summary.schedule_summary_types import ScheduleResultStatus


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


def _freeze_application_status(meta: Dict[str, Any], *, applied: bool, degraded: bool) -> Optional[str]:
    raw_status = str(meta.get("freeze_application_status") or "").strip().lower()
    if raw_status in {"partially_applied", "unapplied", "applied"}:
        return raw_status
    if degraded:
        return "partially_applied" if applied else "unapplied"
    if applied:
        return "applied"
    return None


def _freeze_degradation_reason(*, degraded: bool, application_status: Optional[str]) -> Optional[str]:
    if not degraded:
        return None
    if application_status == "partially_applied":
        return FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE
    return FREEZE_WINDOW_DEGRADED_MESSAGE


def _freeze_degradation_public_code(*, degraded: bool, application_status: Optional[str], meta: Dict[str, Any]) -> Optional[str]:
    if not degraded:
        return None
    raw_code = str(meta.get("freeze_degradation_public_code") or "").strip()
    if raw_code:
        return raw_code
    if application_status == "partially_applied":
        return "freeze_window_partially_applied"
    return "freeze_window_unapplied"


def _compute_completion_status(summary: Any) -> str:
    if getattr(summary, "success", False):
        result_status = ScheduleResultStatus.SUCCESS
    elif int(getattr(summary, "scheduled_ops", 0) or 0) > 0:
        result_status = ScheduleResultStatus.PARTIAL
    else:
        result_status = ScheduleResultStatus.FAILED
    return result_status.value


def _compute_result_status(summary: Any, *, simulate: bool) -> str:
    result_status = _compute_completion_status(summary)
    if simulate:
        return ScheduleResultStatus.SIMULATED.value
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
    application_status = _freeze_application_status(meta, applied=applied, degraded=degraded)
    degradation_reason = _freeze_degradation_reason(
        degraded=degraded,
        application_status=application_status,
    )
    return {
        "enabled": bool(enabled),
        "days": int(days),
        "freeze_state": freeze_state,
        "freeze_applied": bool(applied),
        "freeze_application_status": application_status,
        "freeze_disabled_reason": str(meta.get("freeze_disabled_reason") or "").strip() or None,
        "freeze_degradation_codes": degradation_codes,
        "freeze_degradation_public_code": _freeze_degradation_public_code(
            degraded=degraded,
            application_status=application_status,
            meta=meta,
        ),
        "freeze_degradation_count": int(meta.get("freeze_degradation_count") or 0) if isinstance(meta, dict) else 0,
        "degradation_from_warning_fallback": bool(not has_freeze_meta and bool(freeze_warnings)),
        "degradation_reason": degradation_reason,
    }
