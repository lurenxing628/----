"""R1-E projection responsibilities preserve missing evidence and time boundaries."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS, SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from core.services.workbench.plan_delivery_completeness import completion_evidence
from core.services.workbench.plan_delivery_projection import project_delivery_batch, selected_batch_keys, task_intervals
from core.services.workbench.plan_occupancy import _resource_occupancy


@pytest.mark.parametrize("payload", [
    {"failure_details": None}, {"failure_details": [{}]}, {"failure_details": [{"batch_id": " "}]},
    {"incomplete_batches": []}, {"incomplete_batches": {"count": True, "items": []}},
    {"incomplete_batches": {"count": 1, "items": [{"batch_id": 12}]}},
    {"counts": []}, {"counts": {"failed_ops": -1}},
])
def test_malformed_completion_evidence_is_not_healthy(payload):
    record = {"source": SOURCE_SCHEDULE, "summary": json.dumps(payload)}
    assert completion_evidence(record, 1, {}) == (set(), ["completion_summary_invalid"])


@pytest.mark.parametrize("source,issues", [
    (SOURCE_SCHEDULE, ["completion_summary_missing"]), (SOURCE_CANDIDATE_ROWS, []),
])
def test_missing_summary_retains_legacy_source_distinction(source, issues):
    assert completion_evidence({"source": source, "summary": None}, 1, {}) == (set(), issues)


@pytest.mark.parametrize("count,issues", [(1, []), (True, ["scenario_rows_incomplete"]), (2, ["scenario_rows_incomplete"])])
def test_scenario_completeness_uses_own_exact_row_count(count, issues):
    record = {"source": SOURCE_ADJUSTMENT_SCENARIO_ROWS, "scenario": {"row_count": count},
              "summary": json.dumps({"counts": {"failed_ops": 99}})}
    assert completion_evidence(record, 1, {}) == (set(), issues)


def test_sampled_failure_bucket_never_proves_other_batches_complete():
    record = {"source": SOURCE_SCHEDULE, "summary": json.dumps({
        "incomplete_batches": {"count": 2, "items": [{"batch_id": "B1"}]},
    })}
    assert completion_evidence(record, 1, {}) == (set(), ["completion_summary_sampled"])
    partial = {"B1": datetime(2026, 9, 9, 9)}
    assert completion_evidence(record, 1, partial) == ({"B1"}, ["completion_summary_sampled"])


def test_batch_selection_keeps_points_half_open_and_invalid_rows_visible():
    rows = [{"schedule_id": i, "batch_id": batch, "start_time": start, "end_time": end, "_point_work": point}
            for i, batch, start, end, point in (
                (1, "lower", "2026-09-09T08:00:00", "2026-09-09T08:00:00", True),
                (2, "upper", "2026-09-09T09:00:00", "2026-09-09T09:00:00", True),
                (3, "invalid", "broken", "broken", False),
                (4, "prior", "2026-09-09T07:00:00", "2026-09-09T08:00:00", False),
            )]
    scope = SimpleNamespace(range_start="2026-09-09T08:00:00", range_end="2026-09-09T09:00:00")
    assert selected_batch_keys(rows, task_intervals(rows), scope) == ["invalid", "lower"]


def test_schedule_completion_is_separate_from_missing_due_or_label():
    rows = [{"schedule_id": 1, "op_id": 10, "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T09:00:00"}]
    item = project_delivery_batch({"batch_id": "B1", "part_no": "P1", "part_name": None, "due_date": None},
                                  "batch-ref", rows, [{"op_id": 10}], task_intervals(rows), False, [])
    assert item["schedule_complete"] is True
    assert item["planned_finish"] == "2026-09-09T09:00:00" and item["partial_planned_finish"] is None
    assert item["completeness"] == item["risk"] == "unknown"
    assert item["is_overdue"] is None and item["delay_hours"] is None
    assert item["issues"] == ["due_date_missing", "part_label_missing"]


@pytest.mark.parametrize("known_zero", [False, True])
def test_occupancy_distinguishes_unknown_and_zero_calendar_capacity(known_zero):
    operations = {10: [(datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 9))]}
    resources = {"machine": {"M1": SimpleNamespace(ref="machine-ref")}}
    calendar = {"state": "available", "basis": "global_calendar", "label": "Machine", "windows": [], "issues": []}
    item = _resource_occupancy("machine", "M1", operations, calendar if known_zero else None, resources, "Machine")
    assert item["arranged_hours"] == item["occupied_hours"] == 1
    assert item["overlap_hours"] == 0 and item["utilization"] is None
    assert item["state"] == ("available" if known_zero else "unavailable")
    assert item["available_hours"] == (0 if known_zero else None)
    assert item["capacity_shortfall_hours"] == (1 if known_zero else None)
    assert item["outside_available_hours"] == (1 if known_zero else None)
    assert item["capacity_insufficient"] is (True if known_zero else None)
