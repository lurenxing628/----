"""A reused suffix must equal a separate native decode, including a changed middle."""
from copy import deepcopy
from functools import wraps

import pytest

from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest
from core.algorithms.greedy.dispatch.sgs_checkpoint_tail import DecodeTailReuse
from core.infrastructure.errors import ValidationError
from tests._support.optimizer_end_to_end_cases import case_environment, fixture_data
from tests.resource_dispatch.test_sgs_decode_checkpoint_contract import RUN_CONFIG, _Case


def _dense_data():
    data = fixture_data("tiny_chain")
    batch, op = data["batches"][0], data["operations"][0]
    data["batches"], data["operations"] = [], []
    for index in range(10):
        bid = "B" + str(index)
        data["batches"].append(dict(batch, batch_id=bid, quantity=1))
        for seq in range(1, 4):
            op_id = index * 3 + seq
            data["operations"].append(dict(op, id=op_id, op_code=str(op_id), batch_id=bid,
                                          seq=seq, unit_hours=0.25, setup_hours=0.0))
    return data


@pytest.mark.parametrize("scenario", ["dense", "wide_parallel_chains"])
def test_changed_middle_then_reused_tail_matches_full_decode_twice(scenario):
    data = _dense_data() if scenario == "dense" else fixture_data(scenario)
    with case_environment(data, "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = tuple(op.id for op in sorted(case.operations, key=lambda op: (op.seq, op.id)))
        n = len(order)
        captured = []
        _rows, _summary, before = case.decode(order, checkpoints=DecodeCheckpointRequest([2, n - 5, n], captured.append))
        changed = list(order)
        changed[4], changed[5] = changed[5], changed[4]
        changed = tuple(changed)
        full_rows, full_summary, full = case.decode(changed)
        assert full_summary.failed_ops == 0
        for _repeat in range(2):
            tail = DecodeTailReuse(captured)
            request = DecodeCheckpointRequest([n], lambda checkpoint: None, tail_reuse=tail)
            rows, summary, actual = case.decode(changed, resume=captured[0], checkpoints=request)
            assert actual == full and rows == full_rows and summary.failed_ops == 0
            assert tail.reused_picks == 5 and tail.reason == "exact_state_reconvergence"
        assert case.decode(order)[2] == before


def test_a_changed_future_priority_prevents_early_tail_reuse():
    with case_environment(_dense_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = tuple(op.id for op in sorted(case.operations, key=lambda op: (op.seq, op.id)))
        captured = []
        case.decode(order, checkpoints=DecodeCheckpointRequest([2, 20, len(order)], captured.append))
        changed = list(order)
        changed[24], changed[25] = changed[25], changed[24]
        full = case.decode(tuple(changed))[2]
        tail = DecodeTailReuse(captured)
        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, tail_reuse=tail)
        assert case.decode(tuple(changed), resume=captured[0], checkpoints=request)[2] == full
        assert tail.checks > 0 and tail.reused_picks == 0


def test_tail_input_drift_is_rejected_and_reference_is_not_consumed():
    with case_environment(_dense_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order, captured = case.base_order(), []
        before = case.decode(order, checkpoints=DecodeCheckpointRequest([2, len(order)], captured.append))[2]
        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, tail_reuse=DecodeTailReuse(captured))
        case.operations[0].unit_hours *= 2
        with pytest.raises(ValidationError) as exc:
            case.decode(order, checkpoints=request)
        assert exc.value.details["reason"] == "decode_checkpoint_tail_signature_mismatch"
        case.operations[0].unit_hours /= 2
        assert case.decode(order)[2] == before


def test_decode_can_stop_between_picks_without_mutating_the_checkpoint():
    with case_environment(_dense_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order, captured = case.base_order(), []
        before = case.decode(order, checkpoints=DecodeCheckpointRequest([2, len(order)], captured.append))[2]
        progress_before = deepcopy(captured[0].graph_progress)

        def stop(position):
            if position >= 5:
                raise RuntimeError("local neighborhood ended")

        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, check_budget=stop)
        with pytest.raises(RuntimeError, match="local neighborhood ended"):
            case.decode(order, resume=captured[0], checkpoints=request)
        assert captured[0].graph_progress == progress_before
        assert case.decode(order, resume=captured[0])[2] == before


@pytest.mark.parametrize("scenario", ["shift_pool", "frozen_ready_external"])
def test_auto_assignment_or_external_work_declines_tail_reuse(scenario):
    with case_environment(fixture_data(scenario), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order, captured = case.base_order(), []
        full = case.decode(order, checkpoints=DecodeCheckpointRequest([2, len(order) // 2, len(order)], captured.append))[2]
        tail = DecodeTailReuse(captured)
        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, tail_reuse=tail)
        assert case.decode(order, resume=captured[0], checkpoints=request)[2] == full
        assert tail.reused_picks == 0 and tail.reason == "unsupported_native_fixed_resource_context"


def test_instrumented_internal_dispatch_is_not_bypassed(monkeypatch):
    from core.algorithms.greedy import scheduler as scheduler_module

    with case_environment(_dense_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order, captured = case.base_order(), []
        full = case.decode(order, checkpoints=DecodeCheckpointRequest([2, 20, len(order)], captured.append))[2]
        observed = []
        original = scheduler_module.schedule_internal_operation

        @wraps(original)
        def counting(**kwargs):
            observed.append(kwargs["op"].id)
            return original(**kwargs)

        monkeypatch.setattr(scheduler_module, "schedule_internal_operation", counting)
        tail = DecodeTailReuse(captured)
        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, tail_reuse=tail)
        assert case.decode(order, resume=captured[0], checkpoints=request)[2] == full
        assert len(observed) == len(order) - captured[0].position
        assert tail.reused_picks == 0


def test_local_cutoff_after_the_last_pick_preserves_the_completed_result():
    with case_environment(_dense_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = case.base_order()
        expected = case.decode(order)[2]

        def expires_after_last_pick(position):
            if position >= len(order):
                raise RuntimeError("the completed schedule must survive")

        request = DecodeCheckpointRequest([len(order)], lambda checkpoint: None, check_budget=expires_after_last_pick)
        assert case.decode(order, checkpoints=request)[2] == expected
