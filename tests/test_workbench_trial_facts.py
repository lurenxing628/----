"""Regression tests for trial draft interval facts and unproven zero-length spans."""

from core.models.workbench_trial_codec import dump, load_object
from tests.workbench.trial_support import create, service, trial_case

__all__ = ["trial_case"]


def test_persisted_unproven_zero_length_trial_row_reports_calendar_unproven_without_point_error(trial_case):
    case = trial_case
    draft = create(case)
    row_ref = draft["tasks"][0]["row_ref"]
    task_ref = draft["tasks"][0]["task_ref"]

    raw_current = case.conn.execute(
        "SELECT current_json FROM WorkbenchTrialRows WHERE draft_ref=? AND row_ref=?",
        (draft["draft_ref"], row_ref),
    ).fetchone()[0]
    current = load_object(raw_current)
    current["end"] = current["start"]
    case.conn.execute(
        "UPDATE WorkbenchTrialRows SET current_json=? WHERE draft_ref=? AND row_ref=?",
        (dump(current), draft["draft_ref"], row_ref),
    )
    case.conn.commit()

    projected = service(case.conn).get(draft["draft_ref"])
    assert projected["validation"]["constraints_status"] == "blocked"
    assert projected["validation"]["can_adopt"] is False
    issue_codes = {
        item["code"]
        for item in projected["validation"]["issues"]
        if item.get("task_ref") == task_ref and item["severity"] == "blocker"
    }
    assert "calendar_unproven" in issue_codes

    task = projected["tasks"][0]
    assert task["start"] == task["end"]
    assert "event_kind" not in task
    assert "calendar_unproven" in {item["code"] for item in task["issues"]}
    assert "schedule_time_invalid" in projected["comparison"]["batches"][0]["after"]["issues"]
    assert projected["capacity"]["state"] == "partial"
