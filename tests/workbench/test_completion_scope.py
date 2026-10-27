"""Complete cohorts and remaining requirements use shared delivery/work facts."""

from copy import deepcopy

import pytest

from core.algorithm_runtime.operation_effort import internal_operation_effort
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.completion_scope import (
    attach_remaining_operations,
    completion_groups,
    project_completion_summary,
)
from core.services.workbench.facts.delivery_projection import delivery_summary, project_delivery_batch, task_intervals
from core.services.workbench.facts.preparation_projection import project_operation_effort
from tests._support.algo_operations import make_algo_op, make_batch


def batch_item(ref, *, arranged=(1,), expected=(1,), deferred=(), finish="2026-10-13T12:00:00", due="2026-10-13"):
    batch = {"batch_id": ref, "part_no": "P1", "part_name": "零件", "quantity": 10, "priority": "normal", "due_date": due}
    rows = [{"schedule_id": key, "op_id": key, "batch_id": ref,
             "start_time": "2026-10-13T08:00:00", "end_time": finish} for key in arranged]
    return project_delivery_batch(batch, ref, rows, [{"op_id": key} for key in expected], task_intervals(rows),
                                  False, [], deferred_operation_ids=deferred)


def work_item(ref, batch_ref, *, arranged=False, allocation="unplanned", runtime=True, sequence=1):
    operation = make_algo_op(id=sequence, batch_id=batch_ref, setup_hours=2, unit_hours=0.5)
    effort = internal_operation_effort(operation, make_batch(batch_id=batch_ref, quantity=10)).to_dict() if runtime else None
    standard = {"basis": "archived_operation_standard", "setup_standard_hours": 2, "unit_standard_hours": 0.5,
                "target_quantity": 10, "remaining_quantity": 10, "standard_total_hours": 7,
                "state": "complete", "reason": None}
    row = project_operation_effort(effort, standard, allocation_state=allocation, source="internal",
                                  execution={"execution_state": "unreported", "target_quantity": 10,
                                             "target_basis": "batch", "remaining_quantity": 10})
    return {**row, "operation_ref": ref, "batch_ref": batch_ref, "sequence": sequence, "process_label": "工序",
            "arranged": arranged, "disposition": {"status": "skipped" if allocation == "deferred" else "eligible",
                "issues": [{"code": "material_not_ready", "message": "等待物料。"}] if allocation == "deferred" else []}}


def test_different_partial_results_compare_delivery_only_on_the_nonempty_common_completed_set():
    before = [batch_item("A", finish="2026-10-14T10:00:00"), batch_item("B", arranged=()),
              batch_item("C", finish="2026-10-14T03:00:00")]
    after = [batch_item("A", arranged=()), batch_item("B", finish="2026-10-14T00:30:00"), batch_item("C")]
    first = project_completion_summary(before, [work_item("b", "B")])
    second = project_completion_summary(after, [work_item("a", "A")])
    assert first["complete_batch_refs"] == ["A", "C"] and first["incomplete_batch_refs"] == ["B"]
    assert second["complete_batch_refs"] == ["B", "C"] and second["incomplete_batch_refs"] == ["A"]
    original = deepcopy((before, after))
    pair = common_completed_delivery(before, after)
    assert pair["common_completed_batch_refs"] == ["C"]
    assert pair["common_delivery"]["delay_delta_hours"] == -3
    assert pair["common_delivery"]["overdue_delta_count"] == -1
    assert pair["common_delivery"]["before"]["batch_count"] == pair["common_delivery"]["after"]["batch_count"] == 1
    assert delivery_summary(before)["total_tardiness_hours"] is delivery_summary(after)["total_tardiness_hours"] is None
    assert (before, after) == original
    groups = completion_groups([
        {"candidate_ref": "first", "completion_scope": first},
        {"candidate_ref": "second", "completion_scope": second},
    ])
    assert [row["complete_batch_refs"] for row in groups] == [["A", "C"], ["B", "C"]]


def test_same_completed_group_preserves_distinct_unfinished_operation_prefixes():
    first = project_completion_summary([batch_item("B", expected=(1, 2, 3))], [
        work_item("op-1", "B", arranged=True, allocation="new_schedule"),
        work_item("op-2", "B", sequence=2), work_item("op-3", "B", sequence=3)])
    second = project_completion_summary([batch_item("B", arranged=(1, 2), expected=(1, 2, 3))], [
        work_item("op-1", "B", arranged=True, allocation="new_schedule"),
        work_item("op-2", "B", arranged=True, allocation="new_schedule", sequence=2), work_item("op-3", "B", sequence=3)])
    groups = completion_groups([
        {"candidate_ref": "second", "completion_scope": second},
        {"candidate_ref": "first", "completion_scope": first},
    ])
    assert groups == [{"source_available": True, "complete_batch_refs": [], "candidate_refs": ["first", "second"]}]
    assert first["unplanned_operation_refs"] == ["op-2", "op-3"]
    assert second["unplanned_operation_refs"] == ["op-3"]
    assert first["remaining_work"]["metrics"]["unplanned_setup_hours"]["value"] == 4
    assert second["remaining_work"]["metrics"]["unplanned_setup_hours"]["value"] == 2


def test_remaining_work_keeps_ordinary_deferred_unknown_and_original_measurements_separate():
    items = [batch_item("A"), batch_item("B", expected=(1, 2), deferred=(2,)),
             batch_item("C", arranged=()), batch_item("D", finish=None)]
    work = [work_item("ordinary", "C"), work_item("waiting", "B", allocation="deferred", runtime=False, sequence=2)]
    original = deepcopy((items, work))
    scope = project_completion_summary(items, work, schedulable_coverage={"state": "partial", "missing_count": 1, "deferred_count": 1})
    assert scope["state"] == "partial" and scope["complete_batch_refs"] == ["A"]
    assert scope["incomplete_batch_refs"] == ["B", "C", "D"]
    assert scope["ordinary_incomplete_batch_refs"] == ["C"] and scope["deferred_batch_refs"] == ["B"]
    assert scope["unknown_batch_refs"] == ["D"]
    assert scope["unplanned_operation_refs"] == ["ordinary"] and scope["deferred_operation_refs"] == ["waiting"]
    details = attach_remaining_operations(scope, work)
    batches = {row["batch_ref"]: row for row in details["remaining_batches"]}
    waiting, ordinary = batches["B"]["operations"][0], batches["C"]["operations"][0]
    assert waiting["required_standard_hours"] is None and waiting["standard"]["standard_total_hours"] == 7
    assert waiting["remaining_quantity"] == ordinary["remaining_quantity"] == 10
    assert ordinary["setup_standard_hours"] == 2 and ordinary["processing_standard_hours"] == 5 and ordinary["required_standard_hours"] == 7
    assert waiting["disposition_status"] == "skipped" and waiting["reasons"][0]["code"] == "material_not_ready"
    assert batches["D"]["operations"] == [] and "schedule_time_invalid" in batches["D"]["issues"]
    metrics = scope["remaining_work"]["metrics"]
    assert metrics["pending_setup_hours"]["value"] is None and metrics["pending_setup_hours"]["known_subtotal"] == 2
    assert metrics["pending_setup_hours"]["unknown_count"] == 1
    assert (items, work) == original and scope["schedulable"]["missing_count"] == 1


@pytest.mark.parametrize("case,state,refs", [("empty", "not_applicable", []),
                                             ("unspecified", "not_applicable", ["B"]), ("invalid", "unavailable", ["B"])])
def test_empty_unspecified_and_invalid_common_due_scopes_never_create_zero_benefits(case, state, refs):
    due = "9999-12-31" if case == "unspecified" else None if case == "invalid" else "2026-10-13"
    before = [batch_item("B", due=due)]
    after = [batch_item("B", arranged=() if case == "empty" else (1,), due=due)]
    pair = common_completed_delivery(before, after)
    assert pair["common_completed_batch_refs"] == refs
    common = pair["common_delivery"]
    assert common["before"]["state"] == common["after"]["state"] == state
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None
