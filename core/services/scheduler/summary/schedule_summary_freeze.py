from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.types import ScheduleSummary
from core.models.batch_operation import BatchOperation
from core.models.enums import YesNo
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.contracts.schedule_summary_types import ScheduleResultStatus


def _freeze_window_config_state(cfg: ScheduleConfigSnapshot) -> Tuple[bool, int]:
    enabled = cfg.freeze_window_enabled == YesNo.YES.value
    return enabled, cfg.freeze_window_days


def _freeze_applied(meta: Dict[str, Any], *, frozen_op_ids: Set[int]) -> bool:
    if "freeze_applied" in meta:
        return bool(meta.get("freeze_applied"))
    return bool(frozen_op_ids)


def _freeze_state_name(*, enabled: bool, applied: bool, raw_state: Optional[str]) -> str:
    # 冻结只有严格口径（freeze_window.build_freeze_window_seed 读不出来整次拒绝），状态只会是 active/disabled。
    if raw_state in {"active", "disabled"}:
        return raw_state
    return "active" if enabled and applied else "disabled"


def _compute_completion_status(summary: Optional[ScheduleSummary]) -> str:
    if summary is not None and summary.success:
        result_status = ScheduleResultStatus.SUCCESS
    elif summary is not None and summary.scheduled_ops > 0:
        result_status = ScheduleResultStatus.PARTIAL
    else:
        result_status = ScheduleResultStatus.FAILED
    return result_status.value


def _frozen_batch_ids(operations: List[BatchOperation], *, frozen_op_ids: Set[int]) -> List[str]:
    if not frozen_op_ids:
        return []
    return sorted(
        {
            op.batch_id
            for op in operations
            if op.id and op.id in frozen_op_ids and op.batch_id.strip()
        }
    )


def _freeze_meta_dict(
    cfg: ScheduleConfigSnapshot,
    *,
    frozen_op_ids: Set[int],
    freeze_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    meta = freeze_meta if isinstance(freeze_meta, dict) else {}
    if "freeze_enabled" in meta:
        enabled = bool(meta["freeze_enabled"])
        days = int(meta.get("freeze_days") or 0)
    else:
        enabled, days = _freeze_window_config_state(cfg)
    applied = _freeze_applied(meta, frozen_op_ids=frozen_op_ids)
    return {
        "enabled": bool(enabled),
        "days": int(days),
        "freeze_state": _freeze_state_name(enabled=enabled, applied=applied, raw_state=meta.get("freeze_state")),
        "freeze_applied": bool(applied),
        "freeze_application_status": "applied" if applied else None,
        "freeze_disabled_reason": str(meta.get("freeze_disabled_reason") or "").strip() or None,
    }
