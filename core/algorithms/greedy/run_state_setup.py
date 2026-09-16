"""Run-state preparation for one decode: seeds, readiness gate, and checkpoint resumption."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.algorithm_contracts.ordering import normalize_text_id, parse_ready_date_for_sort
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.slot_overlap_reuse import SlotReuseTimeline
from core.infrastructure.errors import ValidationError

from .dispatch.sgs_checkpoint import CHECKPOINT_FIELD, DecodeCheckpoint
from .external_groups import rebuild_external_group_cache_from_seeds
from .seed import _identity_int, seed_external_group_keys, seed_result_for_output


def _prepare_run_state(
    calendar: Any,
    *,
    batches: Dict[str, Any],
    operations: List[Any],
    seed_results: Optional[List[ScheduleResult]],
    params: Any,
    warnings: List[str],
    algo_stats: Dict[str, Any],
    readiness_gate_enabled: bool,
    strict_mode: bool,
    owned_timelines: bool = True,
) -> ScheduleRunState:
    state = (ScheduleRunState(base_time=params.base_time) if owned_timelines else
             ScheduleRunState(base_time=params.base_time, machine_timeline=SlotReuseTimeline(), operator_timeline={}))
    if bool(readiness_gate_enabled):
        _initialize_ready_progress(calendar, state=state, batches=batches, strict_mode=strict_mode)
    if seed_results:
        _apply_seed_results(state=state, seed_results=seed_results)
        # audit 2026-07-20 A14：seed 注入除资源占用/批次进度外，还要按组键重建外部组缓存，
        # 否则 merged 外协组被部分种入时，未种成员会另起一整段全长组块且零留痕。
        rebuild_external_group_cache_from_seeds(
            seed_results=seed_results,
            seed_group_keys=seed_external_group_keys(seed_results),
            operations=operations,
            external_group_cache=state.external_group_cache,
            warnings=warnings,
            algo_stats=algo_stats,
        )
        warnings.extend(state.seed_resource_warnings())
        increment_counter(algo_stats, "seed_missing_machine_id_count", state.missing_seed_machine_count)
        increment_counter(algo_stats, "seed_missing_operator_id_count", state.missing_seed_operator_count)
    return state


def _initialize_ready_progress(calendar: Any, *, state: ScheduleRunState, batches: Dict[str, Any], strict_mode: bool) -> None:
    for batch_id, batch in batches.items():
        ready_date = parse_ready_date_for_sort(getattr(batch, "ready_date", None), strict_mode=bool(strict_mode))
        if batch_id and ready_date is not None:
            ready_start = datetime(ready_date.year, ready_date.month, ready_date.day, 0, 0, 0)
            # 齐套只设时间下界；日历校验留给实际资源排槽，外协仍按自然日推进。
            state.advance_batch(batch_id, ready_start)


def _apply_seed_results(*, state: ScheduleRunState, seed_results: List[ScheduleResult]) -> None:
    for result in seed_results:
        _validate_seed_result(result)
        _freeze_seed_resources(state, result)
        state.record_seed_result(seed_result_for_output(result))


def _validate_seed_result(result: ScheduleResult) -> None:
    from core.algorithm_contracts.schedule_point_evidence import point_seed_valid
    if not result:
        raise ValidationError("已有排产记录无效，系统已停止排产。", field="seed_results")
    if not isinstance(result.start_time, datetime) or not isinstance(result.end_time, datetime):
        raise ValidationError("已有排产记录的开始时间和结束时间必须是有效时间。", field="seed_results")
    if result.end_time <= result.start_time and not point_seed_valid(result):
        raise ValidationError("已有排产记录的开始时间必须早于结束时间。", field="seed_results")
    op_id = _identity_int(getattr(result, "op_id", 0))
    if op_id <= 0:
        raise ValidationError("已有排产记录缺少有效工序编号，系统已停止排产。", field="seed_results")


def _freeze_seed_resources(state: ScheduleRunState, result: ScheduleResult) -> None:
    from core.algorithm_contracts.schedule_point_evidence import point_seed_valid

    if point_seed_valid(result):
        return
    if (result.source or "").strip().lower() != INTERNAL:
        return
    if not isinstance(result.start_time, datetime) or not isinstance(result.end_time, datetime):
        return
    machine_id = normalize_text_id(result.machine_id)
    operator_id = normalize_text_id(result.operator_id)
    if machine_id:
        occupy_resource(state.machine_timeline, machine_id, result.start_time, result.end_time)
    if operator_id:
        occupy_resource(state.operator_timeline, operator_id, result.start_time, result.end_time)


def resume_run_state(checkpoint: DecodeCheckpoint, *, signature: str, warnings: List[str],
                     dispatch_mode_key: str, graph_ready_context: Any) -> ScheduleRunState:
    """Clone the checkpoint state for this decode; the caller then rebuilds resource quality and replays it.

    The checkpoint's warnings replace the ones collected so far: they were produced by the same
    deterministic parameter/batch/seed normalisation of an identical input (the signature proves it).
    """
    if not isinstance(checkpoint, DecodeCheckpoint):
        raise ValidationError("断点续排需要一个解码断点对象。", field=CHECKPOINT_FIELD,
                              details={"reason": "decode_checkpoint_bad_object"})
    if dispatch_mode_key != "sgs" or graph_ready_context is None:
        raise ValidationError("断点续排只支持图模式下的 SGS 派工。", field=CHECKPOINT_FIELD,
                              details={"reason": "decode_checkpoint_requires_graph_mode"})
    if checkpoint.signature != signature:
        raise ValidationError("断点续排的解码输入与断点不一致。", field=CHECKPOINT_FIELD,
                              details={"reason": "decode_checkpoint_signature_mismatch"})
    warnings[:] = list(checkpoint.warnings)
    return checkpoint.state.clone()


def replay_resumed_demand(state: ScheduleRunState) -> None:
    """After resource quality is initialised for the resumed decode's own operations, replay lifecycle events."""
    types = state.last_op_type_by_machine
    if isinstance(types, MachineTypeState):
        types.replay_demand_events()
