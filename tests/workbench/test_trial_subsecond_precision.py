"""Subsecond plans survive real trial persistence, restart and official adoption."""

from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial.base import _arrangement
from tests.workbench import trial_support
from tests.workbench.trial_adoption_support import INTENT, preview
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import candidate, change, connect, create, official
from tests.workbench.trial_support import service as trial_service

trial_case = trial_support.trial_case


def _fractional_operation(case):
    # Three pieces at 0.001 hours each require exactly 10.8 seconds.
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001 WHERE id=?", (case.op_id,))
    case.conn.commit()


def _save(case, draft):
    return trial_service(case.conn).save(draft["draft_ref"], {"name": "Subsecond trial"},
        draft["write_context"]["write_token"], "trial-subsecond-save-0001")["data"]


@pytest.mark.parametrize("base", ["official", "candidate"])
@pytest.mark.parametrize("start,end", [
    ("2026-09-09T13:00:00", "2026-09-09T13:00:10.800000"),
    ("2026-09-09T13:00:00.123456", "2026-09-09T13:00:10.923456"),
])
def test_fractional_plan_adjust_save_restart_and_adopt_without_rounding(trial_case, base, start, end):
    case = trial_case
    _fractional_operation(case)
    intent = (official(case, start="2026-09-09 08:00:00.400000", end="2026-09-09 08:00:11.200000")
              if base == "official" else candidate(case))
    draft = create(case, intent)
    original = draft["tasks"][0]
    assert datetime.fromisoformat(original["end"]).microsecond
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]

    changed = change(case, draft, start=start)["data"]
    task = changed["tasks"][0]
    assert task["start"] == start
    assert task["end"] == end
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    saved = _save(case, changed)

    restarted = connect(case.path)
    try:
        restored = trial_service(restarted).scenario(saved["scenario_ref"])
        assert restored == saved
        service = adoption_service(restarted)
        checked = service.preview(saved["scenario_ref"])
        assert checked["validation"]["can_adopt"], checked
        result = service.adopt(saved["scenario_ref"], checked["write_context"]["write_token"],
                               "trial-subsecond-adopt-0001", INTENT)
        assert result["ok"] and result["result"] == "committed"
        version = result["data"]["official_plan"]["version"]
        rows = restarted.execute("SELECT start_time,end_time FROM Schedule WHERE version=?", (version,)).fetchall()
        assert [tuple(row) for row in rows] == [(start.replace("T", " "), end.replace("T", " "))]
        assert trial_service(restarted).scenario(saved["scenario_ref"]) == saved
        next_intent = {"base": {"plan_ref": result["data"]["official_plan"]["plan_ref"]}}
        trials = trial_service(restarted)
        next_preview = trials.preview_create(next_intent)
        next_draft = trials.create(next_intent, next_preview["write_context"]["write_token"],
                                   "trial-subsecond-next-draft-0001")["data"]
        assert (next_draft["tasks"][0]["start"], next_draft["tasks"][0]["end"]) == (start, end)
        assert restarted.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restarted.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        restarted.close()


def test_started_execution_anchor_retains_fractional_plan_duration(trial_case):
    case = trial_case
    _fractional_operation(case)
    case.batch("UNSTARTED")
    second = case.operation("UNSTARTED", machine_id="M3", operator_id="O3")
    intent = official(case, ids=[case.op_id, second],
                      start="2026-09-09T08:00:00.400000", end="2026-09-09T08:00:11.200000")
    case.conn.execute("""UPDATE Schedule SET start_time='2026-09-09T13:00:00',end_time='2026-09-09T13:45:00',
        machine_id='M3',operator_id='O3' WHERE op_id=?""", (second,))
    case.conn.commit()
    case.event(case.op_id, "start", time="2026-09-09T09:00:00")
    draft = create(case, intent)
    task = next(task for task in draft["tasks"] if task["batch_id"] == "B1")
    assert task["execution_anchor"]["basis"] == "started_actuals"
    assert task["start"] == task["execution_anchor"]["start"] == "2026-09-09T09:00:00"
    assert task["end"] == task["execution_anchor"]["end"] == "2026-09-09T09:00:10.800000"
    assert task["locked"] and not task["edit_context"]["can_change"]
    saved = _save(case, draft)
    result = adoption_service(case.conn).adopt(saved["scenario_ref"], preview(case, saved),
                                              "trial-subsecond-anchor-adopt-0001", INTENT)
    version = result["data"]["official_plan"]["version"]
    row = case.conn.execute("SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone()
    assert tuple(row) == ("2026-09-09 09:00:00", "2026-09-09 09:00:10.800000")


@pytest.mark.parametrize("raw", [
    "2026-09-09T08:00:00.800000+08:00",
    "2026-09-09T08:00:00.8",
    "2026-09-09T08:00:00.000000",
    "2026-09-09T08:00:00.8000001",
    "2026-09-09X08:00:00.800000",
])
def test_trial_base_does_not_normalize_ambiguous_subsecond_input(raw):
    with pytest.raises(WorkbenchCommandRejected) as error:
        _arrangement({"start_time": raw, "end_time": "2026-09-09T08:00:10.800000"}, {})
    assert error.value.code == "trial_base_time_invalid"


@pytest.mark.parametrize("raw,expected", [
    ("2026-09-09", "2026-09-09T00:00:00"),
    ("2026-09-09T08:30", "2026-09-09T08:30:00"),
    ("2026-09-09 08:30", "2026-09-09T08:30:00"),
])
def test_trial_base_retains_supported_legacy_date_and_minute_times(raw, expected):
    assert _arrangement({"start_time": raw, "end_time": "2026-09-09T09:00:00"}, {})["start"] == expected
