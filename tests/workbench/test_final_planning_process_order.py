"""Frozen process-order contracts; full-entry task-origin evidence is separate."""

from datetime import datetime, timedelta

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_process_order import project_process_order
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from tests.workbench.piece_chain_support import adopt_trial, piece_layout, saved_trial
from tests.workbench.plan_adoption_baseline_support import adopt_candidate, mutate_json
from tests.workbench.round1_piece_point_support import adopt, candidate
from tests.workbench.round1_piece_point_support import point_case as point_case
from tests.workbench.trial_support import official, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def workspace(case, plan, start=None, end=None):
    before = snapshot(case.conn)
    service = WorkbenchPlanQueryService(case.conn)
    with service.read_snapshot():
        result = service.workspace(PlanReadScope(plan["plan_ref"], start, end))
    assert snapshot(case.conn) == before
    return result


def dependencies(data):
    order = data["projections"]["process_order"]
    assert order["state"] == "available" and order["issues"] == []
    by_task = {row["task_ref"]: row for row in order["items"]}
    assert set(by_task) == {row["task_ref"] for row in data["tasks"]}
    labels = {row["operation_ref"]: (row["piece_id"], row["sequence"]) for row in data["tasks"]}
    return {labels[row["operation_ref"]]: {labels[ref] for ref in row["predecessor_operation_refs"]}
            for row in order["items"]}


@pytest.mark.parametrize("unit", [0, .25])
def test_captured_common_piece_order_and_points(point_case, unit):
    case = point_case
    piece_layout(case, unit=unit)
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    data, _ = workspace(case, plan)
    relation = dependencies(data)
    assert relation[None, 10] == set()
    for piece in ("item-A", "item-B", "item-C"):
        assert relation[piece, 20] == {(None, 10)}
        assert relation[piece, 30] == {(piece, 20)}
    assert relation[None, 40] == {(piece, 30) for piece in ("item-A", "item-B", "item-C")}
    assert all((row["start"] == row["end"]) == (unit == 0) for row in data["tasks"])


def test_saved_trial_uses_its_frozen_relations(trial_case):
    case = trial_case
    ids = piece_layout(case)
    first = adopt_candidate(case)
    _, _, saved = saved_trial(case, {"plan_ref": first["plan_ref"]}, op_id=ids[None, 40])
    second = adopt_trial(case, saved)["data"]["official_plan"]
    data, _ = workspace(case, second)
    assert data["projections"]["process_order"]["basis"] == "trial_creation"
    expected = {row["operation_ref"]: row["predecessor_operation_refs"] for row in saved["tasks"]}
    assert {row["operation_ref"]: row["predecessor_operation_refs"] for row in data["projections"]["process_order"]["items"]} == expected


def test_time_slice_retains_complete_relation_identity(trial_case):
    case = trial_case
    piece_layout(case)
    plan = adopt_candidate(case)
    complete, _ = workspace(case, plan)
    task = next(row for row in complete["tasks"] if row["sequence"] == 40)
    start = task["start"]
    end = (datetime.fromisoformat(start) + timedelta(seconds=1)).isoformat()
    selected, _ = workspace(case, plan, start, end)
    assert 0 < len(selected["tasks"]) < len(complete["tasks"])
    assert selected["projections"]["process_order"] == complete["projections"]["process_order"]


def test_current_bom_cannot_rewrite_frozen_process_order(trial_case):
    case = trial_case
    ids = piece_layout(case)
    plan = adopt_candidate(case)
    before, old_stamp = workspace(case, plan)
    case.conn.execute("UPDATE BatchOperations SET seq=90 WHERE id=?", (ids[None, 10],))
    case.conn.commit()
    after, new_stamp = workspace(case, plan)
    assert after["projections"]["process_order"] == before["projections"]["process_order"]
    assert new_stamp != old_stamp


def test_uncaptured_legacy_plan_is_explicit_unavailable(trial_case):
    case = trial_case
    plan = official(case)["base"]
    data, _ = workspace(case, plan)
    order = data["projections"]["process_order"]
    assert order["state"] == "unavailable" and order["basis"] is None and order["items"] == []
    assert order["issues"][0]["code"] == "process_order_not_recorded"


def test_invalid_adoption_evidence_disables_order_and_changes_fingerprint(trial_case):
    case = trial_case
    piece_layout(case)
    plan = adopt_candidate(case)
    before, stamp = workspace(case, plan)
    assert before["projections"]["process_order"]["state"] == "available"
    mutate_json(case.conn, "ScheduleHistory", "result_summary", lambda value: value["proof"].update(facts_hash="bad"),
                "version=?", (plan["version"],))
    after, updated = workspace(case, plan)
    assert after["projections"]["process_order"]["state"] == "unavailable"
    assert after["projections"]["process_order"]["items"] == []
    assert after["projections"]["process_order"]["issues"]
    assert updated != stamp


def test_process_order_requires_transaction_and_complete_payload_budget(trial_case, monkeypatch):
    case = trial_case
    piece_layout(case)
    plan = adopt_candidate(case)
    with pytest.raises(RuntimeError, match="read transaction"):
        project_process_order(case.conn, plan_ref=plan["plan_ref"])
    monkeypatch.setattr("core.services.workbench.plan_projection.MAX_PLAN_RESPONSE_BYTES", 1)
    with WorkbenchPlanQueryService(case.conn).read_snapshot():
        with pytest.raises(WorkbenchCommandRejected) as error:
            project_process_order(case.conn, plan_ref=plan["plan_ref"])
    assert error.value.status == 413
