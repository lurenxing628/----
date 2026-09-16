"""Bulk tail installation preserves native state, history, and interruption boundaries."""
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.greedy.dispatch import sgs_checkpoint_tail as tail_module
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest, snapshot_graph_progress
from core.algorithms.greedy.dispatch.sgs_checkpoint_tail import DecodeTailReuse
from tests._support.optimizer_end_to_end_cases import case_environment
from tests.resource_dispatch.test_sgs_checkpoint_tail import _dense_data
from tests.resource_dispatch.test_sgs_decode_checkpoint_contract import RUN_CONFIG, _Case


def _data(groups=1):
    data = _dense_data()
    for op in data["operations"]:
        group = int(op["batch_id"][1:]) % groups
        op.update(machine_id="M" + str(group), operator_id="O" + str(group),
                  unit_hours=(0.1, 0.2, 0.3)[op["seq"] - 1])
    data["resource_pool"] = {
        "machines_by_op_type": {"TYPE0": ["M" + str(i) for i in range(groups)]},
        "operators_by_machine": {"M" + str(i): ["O" + str(i)] for i in range(groups)},
        "machines_by_operator": {"O" + str(i): ["M" + str(i)] for i in range(groups)},
        "pair_rank": {},
    }
    return data


def _histories(state):
    types = state.last_op_type_by_machine
    return ({key: list(rows) for key, rows in types._entries.items()}, list(types.demand_events))


def _capture(case, order, positions):
    checkpoints = []
    rows, summary, digest = case.decode(order, checkpoints=DecodeCheckpointRequest(positions, checkpoints.append))
    assert summary.success
    return checkpoints, rows, digest


def _record_install(monkeypatch, records):
    original = tail_module.install_reconverged_tail

    def observe(checkpoint, final, **kwargs):
        result = original(checkpoint, final, **kwargs)
        if result:
            state = kwargs["state"]
            records.append((state.clone(), snapshot_graph_progress(kwargs["graph_state"]),
                            dict(kwargs["next_idx"]), state.last_op_type_by_machine.demand))
        return result

    monkeypatch.setattr(tail_module, "install_reconverged_tail", observe)


@pytest.mark.parametrize("groups", [1, 2])
@pytest.mark.parametrize("piece_scope", [False, True])
def test_bulk_terminal_state_equals_full_native_changed_order(monkeypatch, groups, piece_scope):
    with case_environment(_data(groups), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        case.context["piece_scope"] = piece_scope
        order = tuple(op.id for op in sorted(case.operations, key=lambda op: (op.seq, op.id)))
        reference, _rows, _digest = _capture(case, order, [2, 27, len(order)])
        changed = list(order)
        # Change two already-completed batches at the join. Their last ends and
        # changeover-history op_ids must not be overwritten by the reference.
        changed[22], changed[24] = changed[24], changed[22]
        changed = tuple(changed)
        full, full_rows, full_digest = _capture(case, changed, [len(order)])
        records = []
        _record_install(monkeypatch, records)
        tail = DecodeTailReuse(reference)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        rows, summary, digest = case.decode(changed, resume=reference[0], checkpoints=request)
        assert summary.success and rows == full_rows and digest == full_digest
        assert tail.bulk_installs == 1 and tail.reused_picks == 3
        state, progress, next_idx, demand = records[0]
        assert state == full[0].state
        assert _histories(state) == _histories(full[0].state)
        assert progress == full[0].graph_progress and next_idx == full[0].next_idx
        assert state.batch_progress != reference[-1].state.batch_progress
        for field in ("machine_busy_hours", "operator_busy_hours"):
            assert {key: value.hex() for key, value in getattr(state, field).items()} == {
                key: value.hex() for key, value in getattr(full[0].state, field).items()}
        assert demand._by_id == {} and demand._by_token == {} and demand._groups == {}
        assert demand.revision == len(order)


def test_bulk_rows_and_owned_containers_do_not_alias_reference(monkeypatch):
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = case.base_order()
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        original_states = [item.state.clone() for item in reference]
        original_histories = [_histories(item.state) for item in reference]
        original_graphs = [deepcopy(item.graph_progress) for item in reference]
        live_states = []
        original = tail_module.install_reconverged_tail

        def retain(checkpoint, final, **kwargs):
            installed = original(checkpoint, final, **kwargs)
            if installed:
                live_states.append(kwargs["state"])
            return installed

        monkeypatch.setattr(tail_module, "install_reconverged_tail", retain)
        tail = DecodeTailReuse(reference)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        rows, _summary, actual = case.decode(order, resume=reference[0], checkpoints=request)
        assert actual == expected and tail.bulk_installs == 1
        state = live_states[0]
        rows[0].op_code = "mutated prefix"
        rows[-1].op_code = "mutated suffix"
        state.machine_timeline["M0"].clear()
        state.operator_timeline["O0"].clear()
        state.last_op_type_by_machine._entries["M0"].clear()
        state.last_op_type_by_machine.demand_events.clear()
        state.batch_progress.clear()
        for item, before, history, graph in zip(reference, original_states, original_histories, original_graphs):
            assert item.state == before and _histories(item.state) == history and item.graph_progress == graph
        fresh_tail = DecodeTailReuse(reference)
        fresh = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=fresh_tail)
        assert case.decode(order, resume=reference[0], checkpoints=fresh)[2] == expected


@pytest.mark.parametrize("phase", ["start", "before_publish"])
def test_budget_exception_does_not_partly_install_tail(monkeypatch, phase):
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = case.base_order()
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        original = tail_module.install_reconverged_tail
        retained = []

        def stop(position):
            if phase == "start" or position == len(order) - 1:
                raise RuntimeError("bulk preparation expired")

        def observe(checkpoint, final, **kwargs):
            state = kwargs["state"]
            before, histories = state.clone(), _histories(state)
            demand = state.last_op_type_by_machine.demand
            remaining = dict(demand._by_token)
            graph, next_idx = deepcopy(kwargs["graph_state"]), dict(kwargs["next_idx"])
            with pytest.raises(RuntimeError, match="bulk preparation expired"):
                original(checkpoint, final, **kwargs)
            assert state == before and _histories(state) == histories and demand._by_token == remaining
            assert kwargs["graph_state"] == graph and kwargs["next_idx"] == next_idx
            retained.append(True)
            raise RuntimeError("bulk preparation expired")

        monkeypatch.setattr(tail_module, "install_reconverged_tail", observe)
        tail = DecodeTailReuse(reference, check_budget=stop)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        with pytest.raises(RuntimeError, match="bulk preparation expired"):
            case.decode(order, resume=reference[0], checkpoints=request)
        assert retained == [True] and tail.bulk_installs == 0 and tail.reused_picks == 0
        assert case.decode(order, resume=reference[0])[2] == expected


def test_bulk_omits_resource_replay_and_graph_completion_walks(monkeypatch):
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = case.base_order()
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        original = tail_module.install_reconverged_tail
        calls = []

        def profile(frame, event, _arg):
            if event == "call":
                calls.append(frame.f_code.co_name)

        def measure_calls(checkpoint, final, **kwargs):
            previous = sys.getprofile()
            sys.setprofile(profile)
            try:
                return original(checkpoint, final, **kwargs)
            finally:
                sys.setprofile(previous)

        monkeypatch.setattr(tail_module, "install_reconverged_tail", measure_calls)
        tail = DecodeTailReuse(reference)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        assert case.decode(order, resume=reference[0], checkpoints=request)[2] == expected
        assert tail.bulk_installs == 1 and tail.reused_picks == 10
        assert not set(calls).intersection({"occupy_resource", "record_dispatch_success", "_mark_graph_operation_completed"})


@pytest.mark.parametrize("drift", [False, True])
def test_cross_batch_predecessor_ends_are_required_for_tail_reuse(drift):
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        case.context["piece_scope"] = True
        # B9's first operation also waits for B5's last operation.
        case.context["predecessor_op_ids_by_op_id"][28].add(18)
        case.context["successor_op_ids_by_op_id"][18].add(28)
        order = case.base_order()
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        bad_progress = deepcopy(reference[1].graph_progress)
        if drift:
            bad_progress["end_time_by_op_id"][18] += timedelta(seconds=1)
        bad = replace(reference[1], graph_progress=bad_progress)
        tail = DecodeTailReuse([reference[0], bad, reference[-1]])
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        assert case.decode(order, resume=reference[0], checkpoints=request)[2] == expected
        assert tail.checks > 0 and tail.reused_picks == (0 if drift else 10)


def test_seed_result_and_its_occupancy_survive_bulk_tail_installation(monkeypatch):
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        at = schedule_input.start_dt_norm
        case.seeds.append(ScheduleResult(999, "fixed", "DONE", 1, "M0", "O0",
                                         at - timedelta(hours=2), at - timedelta(hours=1),
                                         op_type_name="TYPE0", seed_source="adopted"))
        case.context["fixed_op_ids"].add(999)
        case.context["fixed_op_sources_by_op_id"][999] = "seed_result"
        order = case.base_order()
        reference, rows, expected = _capture(case, order, [2, 20, len(order)])
        records = []
        _record_install(monkeypatch, records)
        tail = DecodeTailReuse(reference)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        actual_rows, summary, digest = case.decode(order, resume=reference[0], checkpoints=request)
        assert actual_rows == rows and digest == expected and summary.scheduled_ops == len(order) + 1
        state, progress, next_idx, _demand = records[0]
        assert state.seed_count == 1 and state == reference[-1].state
        assert _histories(state) == _histories(reference[-1].state)
        assert progress == reference[-1].graph_progress and next_idx == reference[-1].next_idx
        assert tail.bulk_installs == 1 and tail.reused_picks == 10


def test_final_capture_from_another_order_is_not_installed():
    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = tuple(op.id for op in sorted(case.operations, key=lambda op: (op.seq, op.id)))
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        changed = list(order)
        changed[4], changed[5] = changed[5], changed[4]
        other, _rows, _digest = _capture(case, tuple(changed), [len(order)])
        tail = DecodeTailReuse(reference[:2] + other)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        assert case.decode(order, resume=reference[0], checkpoints=request)[2] == expected
        assert tail.reused_picks == 0 and tail.reason == "unsupported_native_tail_snapshot"


def test_instrumented_success_bookkeeping_keeps_formal_dispatch(monkeypatch):
    from core.algorithm_runtime.run_state import ScheduleRunState

    with case_environment(_data(), "min_tardiness", RUN_CONFIG) as schedule_input:
        case = _Case(schedule_input)
        order = case.base_order()
        reference, _rows, expected = _capture(case, order, [2, 20, len(order)])
        original = ScheduleRunState.record_dispatch_success
        calls = []

        def record(state, result):
            calls.append(result.op_id)
            return original(state, result)

        monkeypatch.setattr(ScheduleRunState, "record_dispatch_success", record)
        tail = DecodeTailReuse(reference)
        request = DecodeCheckpointRequest([len(order)], lambda item: None, tail_reuse=tail)
        assert case.decode(order, resume=reference[0], checkpoints=request)[2] == expected
        assert calls == list(order[2:]) and tail.reused_picks == 0
