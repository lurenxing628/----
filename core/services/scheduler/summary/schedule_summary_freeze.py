from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.algorithm_contracts.types import ScheduleSummary
from core.models.batch_operation import BatchOperation
from core.services.scheduler.contracts.schedule_summary_types import ScheduleResultStatus


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


def _freeze_meta_dict(freeze_meta: Dict[str, Any]) -> Dict[str, Any]:
    applied = bool(freeze_meta["freeze_applied"])
    return {
        "enabled": bool(freeze_meta["freeze_enabled"]),
        "days": int(freeze_meta["freeze_days"]),
        "freeze_state": freeze_meta["freeze_state"],
        "freeze_applied": applied,
        "freeze_application_status": "applied" if applied else None,
        "freeze_disabled_reason": str(freeze_meta.get("freeze_disabled_reason") or "").strip() or None,
    }
