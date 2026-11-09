from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.auto_assign_contract import (
    AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL,
    AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
)
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.internal_slot import InternalSlotEstimate, estimate_internal_slot
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse
from core.models.batch import Batch

if TYPE_CHECKING:
    from .dispatch.sgs_score_cache import SgsScoreCache
    from .dispatch.sgs_scoring import SgsCandidateScore


def schedule_internal_operation(
    *,
    calendar: Any,
    algo_stats: Any,
    auto_assign_resources: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    last_op_type_by_machine: MachineTypeState,
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    total_hours_by_op_id: Dict[int, float],
    scored: Optional[SgsCandidateScore],
    overlap_reuse: Optional[SlotOverlapReuse],
    score_cache: Optional[SgsScoreCache],
) -> Tuple[Optional[ScheduleResult], Optional[Dict[str, Any]]]:
    bid = op.batch_id
    machine_id, operator_id, estimate, failure = _resolve_internal_resources(
        algo_stats=algo_stats,
        auto_assign_resources=auto_assign_resources,
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        auto_assign_enabled=auto_assign_enabled,
        resource_pool=resource_pool,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        scored=scored,
    )
    if not machine_id or not operator_id:
        return None, failure

    if estimate is None:
        estimate = _estimate_internal(
            calendar=calendar,
            op=op,
            batch=batch,
            bid=bid,
            machine_id=machine_id,
            operator_id=operator_id,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            last_op_type_by_machine=last_op_type_by_machine,
            total_hours_base=total_hours_by_op_id[op.id],
            overlap_reuse=overlap_reuse,
        )
    if estimate.blocked_by_window:
        return None, _window_blocked_failure(end_time=estimate.end_time, end_dt_exclusive=end_dt_exclusive)

    if occupy_resource(machine_timeline, machine_id, estimate.start_time, estimate.end_time) and score_cache is not None:
        score_cache.observe_occupation(machine_timeline, machine_id, estimate.start_time, estimate.end_time)
    if occupy_resource(operator_timeline, operator_id, estimate.start_time, estimate.end_time) and score_cache is not None:
        score_cache.observe_occupation(operator_timeline, operator_id, estimate.start_time, estimate.end_time)
    return _build_internal_result(op=op, batch_id=bid, machine_id=machine_id, operator_id=operator_id, estimate=estimate), None


def _resolve_internal_resources(
    *,
    algo_stats: Any,
    auto_assign_resources: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    last_op_type_by_machine: MachineTypeState,
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    scored: Optional[SgsCandidateScore],
) -> Tuple[str, str, Optional[InternalSlotEstimate], Optional[Dict[str, Any]]]:
    # 未指定的设备或人员只拼作 None；优化器的资源变体只写入资质合格的真实组合。
    machine_id, operator_id = op.machine_id, op.operator_id
    if machine_id and operator_id:
        return machine_id, operator_id, (scored.estimate if scored is not None else None), None
    if not auto_assign_enabled or resource_pool is None:
        increment_counter(algo_stats, "internal_missing_resource_without_auto_assign_count")
        return "", "", None, {"code": "missing_internal_resource", "source": INTERNAL}

    increment_counter(algo_stats, "internal_auto_assign_attempt_count")
    if scored is not None:
        if scored.resources is not None:
            # The scoring probe of this very round already chose the pair and its slot against the unchanged state.
            increment_counter(algo_stats, "internal_auto_assign_success_count")
            return scored.resources[0], scored.resources[1], scored.estimate, None
        if scored.auto_assign_reason == AUTO_ASSIGN_REASON_WINDOW_BLOCKED:
            increment_counter(algo_stats, "auto_assign_window_blocked_count")
            increment_counter(algo_stats, "internal_auto_assign_failed_count")
            return "", "", None, _auto_assign_failure_detail(reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED)

    attempt = auto_assign_resources(
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
    )
    if attempt.machine_id and attempt.operator_id:
        increment_counter(algo_stats, "internal_auto_assign_success_count")
        return attempt.machine_id, attempt.operator_id, attempt.estimate, None
    increment_counter(algo_stats, "internal_auto_assign_failed_count")
    return "", "", None, _auto_assign_failure_detail(reason=attempt.reason)


def _auto_assign_failure_detail(*, reason: str) -> Dict[str, Any]:
    if reason == AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL:
        code = "auto_assign_resource_pool_incomplete"
    elif reason == AUTO_ASSIGN_REASON_WINDOW_BLOCKED:
        code = "auto_assign_window_blocked"
    else:
        code = "auto_assign_no_resource_combination"
    return {"code": code, "source": INTERNAL, "auto_assign_reason": reason}


def _estimate_internal(
    *,
    calendar: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    bid: str,
    machine_id: str,
    operator_id: str,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    last_op_type_by_machine: Optional[MachineTypeState],
    total_hours_base: float,
    overlap_reuse: Optional[SlotOverlapReuse],
) -> InternalSlotEstimate:
    return estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id=machine_id,
        operator_id=operator_id,
        base_time=base_time,
        prev_end=batch_progress.get(bid, base_time),
        machine_timeline=machine_timeline.get(machine_id) or [],
        operator_timeline=operator_timeline.get(operator_id) or [],
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
        last_op_type_by_machine=last_op_type_by_machine,
        abort_after=None,
        total_hours_base=total_hours_base,
        overlap_reuse=overlap_reuse,
    )


def _window_blocked_failure(*, end_time: datetime, end_dt_exclusive: Optional[datetime]) -> Dict[str, Any]:
    deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d") if end_dt_exclusive else "-"
    return {
        "code": "schedule_window_exceeded",
        "source": INTERNAL,
        "deadline": deadline,
        "estimated_end_time": end_time.strftime("%Y-%m-%d %H:%M"),
    }


def _build_internal_result(*, op: OpForScheduleAlgo, batch_id: str, machine_id: str, operator_id: str, estimate: Any) -> ScheduleResult:
    return ScheduleResult(
        op_id=op.id,
        op_code=op.op_code,
        batch_id=batch_id,
        seq=op.seq,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=estimate.start_time,
        end_time=estimate.end_time,
        source=INTERNAL,
        op_type_name=op.op_type_name,
        op_type_id=op.op_type_id,
    )
