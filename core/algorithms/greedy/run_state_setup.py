"""Run-state preparation for one decode: seeds, readiness gate, and checkpoint resumption."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.run_state import ScheduleRunState
from core.errors import ValidationError

from .dispatch.sgs_checkpoint import CHECKPOINT_FIELD, DecodeCheckpoint
from .schedule_params import ScheduleParams
from .schedule_preparation import NativeSchedulePreparation


def prepare_run_state(
    *,
    prepared_inputs: NativeSchedulePreparation,
    params: ScheduleParams,
    warnings: List[str],
    algo_stats: Dict[str, Any],
    readiness_gate_enabled: bool,
) -> ScheduleRunState:
    state = ScheduleRunState(base_time=params.base_time)
    state.readiness_gate_enabled = readiness_gate_enabled
    if readiness_gate_enabled:
        _initialize_ready_progress(
            state=state,
            ready_starts=prepared_inputs.parsed_ready_starts(),
        )
    if prepared_inputs.seed_applications:
        for result, machine_id, operator_id, segments in prepared_inputs.seed_applications:
            if segments:
                for start, end, segment_machine, segment_operator in segments:
                    occupy_resource(state.machine_timeline, segment_machine, start, end)
                    occupy_resource(state.operator_timeline, segment_operator, start, end)
            else:
                if machine_id:
                    occupy_resource(state.machine_timeline, machine_id, result.start_time, result.end_time)
                if operator_id:
                    occupy_resource(state.operator_timeline, operator_id, result.start_time, result.end_time)
            state.record_seed_result(result, segments=segments)
        state.external_group_cache.update(prepared_inputs.seed_external_group_cache)
        warnings.extend(state.seed_resource_warnings())
        increment_counter(algo_stats, "seed_missing_machine_id_count", state.missing_seed_machine_count)
        increment_counter(algo_stats, "seed_missing_operator_id_count", state.missing_seed_operator_count)
    return state


def _initialize_ready_progress(
    *,
    state: ScheduleRunState,
    ready_starts: Dict[str, Optional[datetime]],
) -> None:
    for batch_id, ready_start in ready_starts.items():
        if ready_start is not None:
            state.advance_batch(batch_id, ready_start)


def resume_run_state(checkpoint: DecodeCheckpoint, *, signature: Tuple[Any, ...], warnings: List[str],
                     dispatch_mode_key: str, graph_ready_context: Any) -> ScheduleRunState:
    """Clone the checkpoint state for this decode; the caller then rebuilds resource quality and replays it.

    The checkpoint's warnings replace the ones collected so far: they were produced by the same
    deterministic parameter/batch/seed normalisation of an identical input (the signature proves it).
    """
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
    state.last_op_type_by_machine.replay_demand_events()
