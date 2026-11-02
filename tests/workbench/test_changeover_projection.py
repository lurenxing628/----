"""Actual type identity, full-sequence predecessors and incomplete event facts."""

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.changeover_events import count_known_changeovers
from core.algorithm_runtime.resource_quality import MachineTypeState, slot_changeover_penalty
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.runtime_state import update_machine_last_state
from core.algorithms.greedy.internal_operation import _build_internal_result
from core.services.scheduler.run.freeze_window_seed_rows import build_seed_results
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_result_item
from core.services.workbench.facts import changeovers
from core.services.workbench.facts.changeovers import changeover_projection, subject_arrangements
from core.services.workbench.facts.decision_metrics import metric_definitions, metric_delta
from core.services.workbench.facts.resource_intervals import task_interval
from core.services.workbench.run.decision_changeovers import DecisionChangeovers
from tests._support.algo_operations import make_algo_op

DAY = "2026-09-09"
MACHINE = {"ref": "machine:one", "label": "归档设备"}


def at(hour):
    return DAY + "T" + hour


def task(ref, type_ref, label, start, end, **values):
    return {"row_ref": "row:" + ref, "operation_ref": "operation:" + ref, "source": "internal", "machine": MACHINE,
            "process_type_ref": type_ref, "process_type_label": label, "start": start, "end": end, **values}


def test_actual_type_identity_drives_shared_events_and_runtime_result_seed_count(monkeypatch):
    rows = [task("a", "type:T1", "车削", at("08:00:00"), at("09:00:00")),
            task("b", "type:T1", "精车", at("09:00:00"), at("10:00:00")),
            task("c", "type:T2", "精车", at("10:00:00"), at("11:00:00")),
            task("point", "type:T3", "磨削", at("09:30:00"), at("09:30:00"), event_kind="point", occupies_resources=False),
            task("external", "type:T3", "磨削", at("09:00:00"), at("10:00:00"), source="external")]
    intervals = {row["row_ref"]: task_interval(row) for row in rows}

    def unexpected_parse(_row):
        pytest.fail("切换应复用该来源已核实的区间。")

    with monkeypatch.context() as scoped:
        scoped.setattr(changeovers, "task_interval", unexpected_parse)
        projected = changeover_projection(rows, task_intervals=intervals)
        assert subject_arrangements(rows, {row["operation_ref"] for row in rows}, task_intervals=intervals) == rows[:3]
    assert projected["state"] == "complete" and projected["count"] == projected["known_count"] == 1
    assert projected["changed_machine_count"] == projected["known_changed_machine_count"] == 1
    event = projected["events"][0]
    assert (event["previous_operation_ref"], event["next_operation_ref"]) == ("operation:b", "operation:c")
    assert event["previous_type"] == event["next_type"] == "精车"
    assert event["previous_type_ref"] == "type:T1" and event["next_type_ref"] == "type:T2"
    # Fresh internal results and frozen seed coercion carry real IDs into the
    # same event rule, including same ID/different name and different ID/same name.
    operations = [make_algo_op(id=index + 1, op_code=str(index), seq=index + 1, op_type_id=type_ref, op_type_name=label)
                  for index, (type_ref, label) in enumerate((("T1", "车削"), ("T1", "精车"), ("T2", "精车")))]
    first = _build_internal_result(op=operations[0], batch_id="B1", machine_id="M1", operator_id="O1",
                                  estimate=SimpleNamespace(start_time=datetime.fromisoformat(rows[0]["start"]),
                                                           end_time=datetime.fromisoformat(rows[0]["end"])))
    seeds = build_seed_results({2, 3}, op_by_id={op.id: op for op in operations}, seed_tmp={
        index + 1: {"row": {"machine_id": "M1", "operator_id": "O1"},
                    "start_time": datetime.fromisoformat(rows[index]["start"]), "end_time": datetime.fromisoformat(rows[index]["end"])}
        for index in (1, 2)})
    results = [first] + [coerce_seed_result_item(row, idx=index) for index, row in enumerate(seeds)]
    assert count_known_changeovers({"M1": list(reversed(results))}) == projected["count"]
    state, ends = MachineTypeState(), {}
    update_machine_last_state(last_end_by_machine=ends, last_op_type_by_machine=state, machine_id="M1",
                              start_time=first.start_time, end_time=first.end_time, op_id=first.op_id,
                              op_type_name=first.op_type_name, op_type_id=first.op_type_id, seed_mode=False)
    same = slot_changeover_penalty(state, op=operations[1], machine_id="M1", start=results[1].start_time,
                                    end=results[1].end_time)
    different = slot_changeover_penalty(state, op=make_algo_op(id=3, op_type_id="T2", op_type_name="车削"),
                                         machine_id="M1", start=results[1].start_time, end=results[1].end_time)
    assert same == 0 and different == 1
    # A point event, fresh or seeded, is an event only: no busy hours, tail end, tail type or neighbour row.
    point = datetime.fromisoformat(at("09:30:00"))
    point_result = replace(first, op_id=4, op_code="point", start_time=point, end_time=point,
                           op_type_name="磨削", op_type_id="T3")
    run = ScheduleRunState(base_time=first.start_time)
    run.record_dispatch_success(first)
    run.record_dispatch_success(point_result)
    run.record_seed_result(replace(point_result, op_id=5), occupancies=())
    assert run.last_end_by_machine == {"M1": first.end_time}
    assert dict(run.last_op_type_by_machine) == {"M1": first.op_type_name}
    assert run.machine_busy_hours == {"M1": 1.0} and run.operator_busy_hours == {"O1": 1.0}
    assert slot_changeover_penalty(run.last_op_type_by_machine, op=operations[1], machine_id="M1", start=point,
                                   end=results[2].end_time) == 0
    assert slot_changeover_penalty(run.last_op_type_by_machine, op=operations[2], machine_id="M1", start=point, end=point) == 0
    point_only = ScheduleRunState(base_time=point)
    point_only.record_dispatch_success(point_result)
    assert point_only.last_end_by_machine == {} and dict(point_only.last_op_type_by_machine) == {}
    assert slot_changeover_penalty(point_only.last_op_type_by_machine, op=operations[1], machine_id="M1", start=point,
                                   end=results[2].end_time) == 0
    assert slot_changeover_penalty(None, op=operations[1], machine_id="M1", start=point, end=results[2].end_time) == 0


def test_window_uses_next_start_and_retains_full_sequence_predecessor():
    rows = [task("before", "T1", "车削", at("07:00:00"), at("08:00:00")),
            task("inside", "T2", "铣削", at("08:00:00"), at("09:00:00")),
            task("right", "T1", "车削", at("10:00:00"), at("11:00:00"))]
    result = changeover_projection(rows, start=at("08:00:00"), end=at("10:00:00"),
                                   next_operation_refs=["operation:inside", "operation:right"])
    assert result["count"] == 1 and len(result["events"]) == 1
    event = result["events"][0]
    assert event["next_start"] == at("08:00:00") and event["previous_start"] == at("07:00:00")
    assert event["previous_row_ref"] == "row:before" and event["next_row_ref"] == "row:inside"
    assert changeover_projection(rows, start=at("09:00:00"), end=at("10:00:00"))["count"] == 0
    subjects = {"operation:inside", "operation:right"}
    assert subject_arrangements(rows, subjects, task_intervals={row["row_ref"]: task_interval(row) for row in rows}) == rows[1:]
    missing = rows[2:]
    source = SimpleNamespace(computation_key=lambda key: key,
        analysis_tasks=lambda key: rows if key == "reference" else missing,
        baseline={"state": "available"}, result_available=lambda key: True, operation_refs=subjects,
        scope={"range_start": at("08:00:00"), "range_end": at("10:00:00")},
        task_intervals=lambda key: {row["row_ref"]: task_interval(row) for row in (rows if key == "reference" else missing)})
    engine = DecisionChangeovers(source)
    before, after = (engine.metrics(key)["type_changeover_count"] for key in ("reference", "candidate"))
    definition = next(row for row in metric_definitions() if row["key"] == "type_changeover_count")
    difference = metric_delta(definition, after, before)
    assert difference["state"] == "different_coverage" and difference["value"] is None


def test_duplicate_operation_segments_keep_raw_rows_without_self_conflicts():
    rows = [task("a", "T1", "车削", at("08:00:00"), at("10:00:00")),
            task("a2", "T1", "车削", at("09:00:00"), at("11:00:00"), operation_ref="operation:a"),
            task("b", "T2", "铣削", at("11:00:00"), at("12:00:00"))]
    normal = changeover_projection(rows)
    assert normal["count"] == 1 and normal["conflict"] is False
    assert normal["events"][0]["previous_row_ref"] == "row:a2"
    rows[-1]["start"] = at("10:30:00")
    conflicting = changeover_projection(rows)
    assert conflicting["state"] == "partial" and conflicting["count"] is None
    assert conflicting["known_count"] == 1 and conflicting["conflict"] is True and conflicting["conflict_count"] == 1
    assert conflicting["events"][0]["overlap"] is True and conflicting["events"][0]["state"] == "partial"


def test_blank_type_segment_stays_unknown_without_making_its_operation_inconsistent():
    rows = [task("a", "", "车削", at("08:00:00"), at("09:00:00")),
            task("a2", "T1", "车削", at("09:00:00"), at("10:00:00"), operation_ref="operation:a"),
            task("b", "T2", "铣削", at("10:00:00"), at("11:00:00"))]
    result = changeover_projection(rows)
    assert [(item["code"], item["row_ref"]) for item in result["issues"]] == [("process_type_unknown", "row:a")]
    assert result["count"] is None and result["known_count"] == 1
    assert (result["events"][0]["previous_row_ref"], result["events"][0]["next_row_ref"]) == ("row:a2", "row:b")


def test_missing_type_is_a_barrier_and_missing_time_does_not_invent_adjacency():
    rows = [task("a", "T1", "车削", at("08:00:00"), at("09:00:00")),
            task("missing", None, "精车", at("09:00:00"), at("10:00:00")),
            task("c", "T2", "铣削", at("10:00:00"), at("11:00:00"))]
    result = changeover_projection(rows)
    assert result["count"] is None and result["known_count"] == 0 and result["events"] == []
    assert result["unknown_count"] == 1 and result["issues"][0]["code"] == "process_type_unknown"
    rows[1].update(start=None, end=None, process_type_ref="T2")
    unknown_time = changeover_projection(rows, task_intervals={row["row_ref"]: task_interval(row) for row in rows})
    assert unknown_time["count"] is None and unknown_time["known_count"] == 0 and unknown_time["events"] == []
    assert unknown_time["conflict"] is None
    missing_source = changeover_projection([], work_available=False)
    assert missing_source["count"] is missing_source["known_count"] is None and missing_source["state"] == "unavailable"
    known_empty = changeover_projection([])
    assert known_empty["count"] == known_empty["known_count"] == 0 and known_empty["state"] == "complete"
