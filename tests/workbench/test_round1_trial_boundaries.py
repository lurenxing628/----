"""R1-J characterization of trial relations, occupancy and saved projections."""

from collections import defaultdict
from copy import deepcopy
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial_constraints import _outside_intervals, relation_issues
from core.services.workbench.trial_facts import live_context
from core.services.workbench.trial_projection import tasks_projection
from core.services.workbench.trial_validation import TrialValidator
from core.services.workbench.zero_duration import PointEventError
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.ea_zero_duration_support import adopt, point_candidate
from tests.workbench.trial_support import create, official, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def _at(hour):
    return f"2026-09-09T{hour:02d}:00:00"


def _relation_row(ref, start, end, predecessors=(), *, piece=None, group=None):
    return {"operation_ref": ref, "task_ref": "task-" + ref,
            "current": {"start": _at(start), "end": _at(end)},
            "original": {"operation": {"piece_id": piece}, "external_group": group,
                         "predecessor_operation_refs": list(predecessors)}}


def test_join_checks_every_piece_and_keeps_related_task_identity():
    rows = [_relation_row("root", 8, 9),
            _relation_row("left", 9, 10, ["root"], piece="A"),
            _relation_row("right", 9, 11, ["root"], piece="B"),
            _relation_row("join", 10, 12, ["left", "right"])]
    before = deepcopy(rows)
    problems = relation_issues(rows, {"execution": {}})
    assert [(row["code"], row["task_ref"], row["related_task_ref"]) for row in problems] == [
        ("precedence_violation", "task-join", "task-right")]
    assert rows == before
    rows[-1]["current"]["start"] = _at(11)
    assert relation_issues(rows, {"execution": {}}) == []


@pytest.mark.parametrize("state,finish,expected", [
    (None, None, ["predecessor_missing"]),
    ("partial", _at(9), ["predecessor_missing"]),
    ("complete", None, ["predecessor_missing"]),
    ("complete", _at(11), ["precedence_violation"]),
    ("complete", _at(10), []),
])
def test_missing_predecessor_needs_confirmed_whole_operation_finish(state, finish, expected):
    execution = {} if state is None else {"previous": {"execution_state": state, "confirmed_finish": finish}}
    row = _relation_row("next", 10, 12, ["previous"])
    problems = relation_issues([row], {"execution": execution})
    assert [item["code"] for item in problems] == expected
    assert all(item["task_ref"] == "task-next" and "related_task_ref" not in item for item in problems)


@pytest.mark.parametrize("same_piece,same_group,mode,start,expected", [
    (True, True, "merged", 8, []),
    (True, True, "merged", 9, ["external_group_split"]),
    (False, True, "merged", 8, ["precedence_violation"]),
    (True, False, "merged", 8, ["precedence_violation"]),
    (True, True, "sequential", 8, ["precedence_violation"]),
])
def test_merged_external_cycle_exception_stays_with_exact_piece(same_piece, same_group, mode, start, expected):
    previous = _relation_row("previous", 8, 10, piece="A", group={"group_id": "G", "merge_mode": "merged"})
    row = _relation_row("next", start, 10, ["previous"], piece="A" if same_piece else "B",
                        group={"group_id": "G" if same_group else "H", "merge_mode": mode})
    assert [item["code"] for item in relation_issues([previous, row], {"execution": {}})] == expected


def _scheduled(op_id, version, row_id, start, end):
    return {"op_id": op_id, "version": version, "id": row_id, "start_time": start, "end_time": end,
            "machine_id": "M1", "operator_id": "O1"}


def test_outside_scope_uses_latest_version_and_row_without_hiding_bad_intervals():
    schedule = [_scheduled(2, 2, 3, _at(13), _at(14)), _scheduled(2, 1, 1, _at(8), _at(12)),
                _scheduled(1, 3, 4, _at(8), _at(9)), _scheduled(2, 2, 2, _at(10), _at(11)),
                _scheduled(3, 1, 5, _at(14), _at(15)), _scheduled(4, 1, 6, "bad", _at(16))]
    refs = [{"source_key": str(op), "ref": "op-" + str(op), "kind": "operation", "active": active}
            for op, active in ((1, 1), (2, 1), (3, 0), (4, 1))]
    live = {"facts": {"tables": {"Schedule": schedule, "WorkbenchPlanSourceRefs": refs}}}
    before, occupied = deepcopy(live), defaultdict(list)
    problems = _outside_intervals(occupied, [{"operation_ref": "op-1"}], live)
    assert [item["code"] for item in problems] == ["outside_scope_interval_invalid"]
    expected = [(datetime.fromisoformat(_at(13)), datetime.fromisoformat(_at(14)), "op-2", None),
                (datetime.fromisoformat(_at(14)), datetime.fromisoformat(_at(15)), 3, None)]
    assert occupied == {("machine", "M1"): expected, ("operator", "O1"): expected}
    assert live == before


@pytest.mark.parametrize("proven", [False, True])
def test_outside_point_requires_real_adoption_evidence_and_never_occupies(trial_case, proven):
    case = trial_case
    if proven:
        adopt(case, point_candidate(case))
    else:
        official(case, start=_at(8), end=_at(8))
    live = live_context(case.conn, [])
    before, occupied = snapshot(case.conn), defaultdict(list)
    problems = _outside_intervals(occupied, [], live, conn=case.conn)
    assert [item["code"] for item in problems] == ([] if proven else ["outside_scope_point_unproven"])
    assert occupied == {}
    no_connection = _outside_intervals(occupied, [], live)
    assert [item["code"] for item in no_connection] == ["outside_scope_interval_invalid"]
    assert occupied == {} and snapshot(case.conn) == before


def _stored_trial(case):
    second = case.operation(seq=2)
    draft = create(case, official(case, ids=[case.op_id, second]))
    head, rows = WorkbenchTrialRepository(case.conn).get(draft["draft_ref"])
    live = live_context(case.conn, [row["operation_ref"] for row in rows])
    return draft, head, rows, live


def test_projection_keeps_order_count_identity_changes_and_issue_links(trial_case):
    draft, _, rows, live = _stored_trial(trial_case)
    projected = tasks_projection(rows, draft["draft_ref"], draft["validation"], live)
    assert projected == draft["tasks"]
    rows[0]["current"]["machine_id"] = "M2"
    before = deepcopy(rows)
    projected = tasks_projection(rows, draft["draft_ref"], draft["validation"], live)
    assert len(projected) == 2
    identity = ("task_ref", "row_ref", "operation_ref", "source_task_ref", "source_row_ref", "original")
    for task, old in zip(projected, draft["tasks"]):
        assert {key: task[key] for key in identity} == {key: old[key] for key in identity}
        assert task["issues"] == [item for item in draft["validation"]["issues"]
                                  if task["task_ref"] in (item.get("task_ref"), item.get("related_task_ref"))]
    assert [task["changed"] for task in projected] == [True, False]
    assert projected[1]["predecessor_refs"] == [projected[0]["task_ref"]]
    assert rows == before


@pytest.mark.parametrize("end", ["invalid-time", _at(7), _at(8)])
def test_projection_never_drops_or_repairs_an_invalid_timing_row(trial_case, end):
    draft, _, rows, live = _stored_trial(trial_case)
    rows[0]["current"]["end"] = end
    before = deepcopy(rows)
    if end == rows[0]["current"]["start"]:
        with pytest.raises(PointEventError) as error:
            tasks_projection(rows, draft["draft_ref"], draft["validation"], live)
        assert error.value.code == "point_evidence_missing"
    else:
        tasks = tasks_projection(rows, draft["draft_ref"], draft["validation"], live)
        assert len(tasks) == len(rows) == 2
        assert tasks[0]["end"] == end and tasks[0]["changed"] is True
    assert rows == before


def test_projection_preserves_unknown_hours_and_raw_display_evidence(trial_case):
    draft, _, rows, live = _stored_trial(trial_case)
    rows[0]["original"]["operation"]["unit_hours"] = None
    rows[0]["original"]["batch"]["part_no"] = b"\x00invalid\xff"
    before = deepcopy(rows)
    tasks = tasks_projection(rows, draft["draft_ref"], draft["validation"], live)
    assert len(tasks) == 2
    task = tasks[0]
    assert task["duration_reason"]["code"] == "hours_missing"
    assert task["hours"]["total_hours"] is None and task["hours"]["quantity"] is None
    assert task["edit_context"]["can_change"] is False
    assert task["part_no"] is None
    assert [(item["field"], item["storage_type"]) for item in task["data_gaps"]] == [("part_no", "bytes")]
    assert rows == before


@pytest.mark.parametrize("kind", ["machine", "operator"])
@pytest.mark.parametrize("invalid", ["missing", "inactive", "wrong_kind"])
def test_adjustment_rejects_missing_inactive_or_wrong_resource_kind(trial_case, kind, invalid):
    case = trial_case
    _, head, rows, live = _stored_trial(case)
    intent = {"machine_ref": case.ref("machine", "M2"), "operator_ref": case.ref("operator", "O2"), "start": _at(13)}
    if invalid == "missing":
        intent[kind + "_ref"] = "f" * 48
    elif invalid == "wrong_kind":
        intent[kind + "_ref"] = intent["operator_ref" if kind == "machine" else "machine_ref"]
    else:
        entity = next(item for item in live["facts"]["tables"]["WorkbenchEntityRefs"] if item["ref"] == intent[kind + "_ref"])
        entity["active"] = 0
    before, original = snapshot(case.conn), deepcopy(rows)
    validator = TrialValidator(case.conn, head["admission"], rows, live)
    with pytest.raises(WorkbenchCommandRejected) as error:
        validator.adjusted(rows[0], intent)
    assert error.value.code == "entity_not_found"
    assert rows == original and snapshot(case.conn) == before
