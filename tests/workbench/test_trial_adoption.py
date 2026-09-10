"""Real official append, truthful scenario provenance and retained prior SQLite rows."""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.trial_adoption_support import (
    INTENT,
    KEY,
    assert_retained,
    full_plan,
    preview,
    saved_scenario,
    service,
)
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import candidate, snapshot
from tests.workbench.trial_support import service as trial_service


@pytest.mark.parametrize("base", ["official", "candidate"])
def test_real_append_exact_saved_arrangement_and_identity(trial_case, base):
    case = trial_case
    saved = saved_scenario(case, candidate(case) if base == "candidate" else None)
    token = preview(case, saved)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    assert result["ok"] and result["result"] == "committed" and not result["replayed"]
    data = result["data"]
    assert data["scenario_ref"] == saved["scenario_ref"] and data["draft_ref"] == saved["draft_ref"]
    assert "candidate_ref" not in data and "source_run_ref" not in data["official_plan"]
    plan = data["official_plan"]
    assert plan["kind"] == "official" and plan["version"] == (2 if base == "official" else 1)
    assert plan["source_scenario_ref"] == saved["scenario_ref"]
    row = case.conn.execute("SELECT * FROM Schedule WHERE version=?", (plan["version"],)).fetchone()
    assert (row["machine_id"], row["operator_id"]) == ("M2", "O2")
    assert row["start_time"] == saved["tasks"][0]["start"].replace("T", " ")
    assert row["end_time"] == saved["tasks"][0]["end"].replace("T", " ")
    for text, in case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (plan["version"],)):
        audit = json.loads(text)
        assert audit["scenario_ref"] == saved["scenario_ref"] and audit["draft_ref"] == saved["draft_ref"]
        assert "candidate_ref" not in audit and audit["source"] == "workbench_trial_adoption"
        assert audit["declared_operator"] == INTENT["declared_operator"]
        assert audit["application_operator"] != INTENT["declared_operator"]
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='adopt_trial_scenario'").fetchone()[0] == 1
    assert trial_service(case.conn).scenario(saved["scenario_ref"]) == saved
    assert_retained(before, snapshot(case.conn))
    unchanged = snapshot(case.conn)
    replay = service(case.conn, False).adopt(saved["scenario_ref"], "expired-after-restart", KEY, INTENT)
    assert replay["receipt_ref"] == result["receipt_ref"] and replay["replayed"]
    assert snapshot(case.conn) == unchanged
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).adopt(saved["scenario_ref"], token, KEY + "different", INTENT)
    assert error.value.code == "snapshot_stale" and snapshot(case.conn) == unchanged


def test_narrow_display_scope_does_not_trim_adopted_full_snapshot(trial_case):
    case = trial_case
    value, _ = full_plan(case)
    value["scope"] = {"query": "not-a-visible-task", "range_start": "2026-09-10T08:00:00", "range_end": "2026-09-10T09:00:00"}
    saved = saved_scenario(case, value, changed=False)
    result = service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), KEY, INTENT)
    assert saved["task_count"] == result["data"]["row_count"] == 2
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=2").fetchone()[0] == 2


@pytest.mark.parametrize("state", ["locked", "actual", "legacy"])
def test_old_plans_execution_and_sqlite_types_retained(trial_case, state):
    case = trial_case
    value, _ = full_plan(case)
    case.conn.execute("UPDATE Parts SET part_name=?", (b"\x00\xffold-label",))
    if state == "locked":
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    if state == "actual":
        case.command("create", case.task(1, case.op_id), case.values(quantity=3, actual_end="2026-09-09T11:00:00"))
    elif state == "legacy":
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish", quantity=3, time="2026-09-09T11:00:00")
    saved = saved_scenario(case, value, changed=False)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), KEY, INTENT)
    assert result["data"]["row_count"] == 2
    assert_retained(before, snapshot(case.conn))
    assert case.conn.execute("SELECT typeof(part_name),part_name FROM Parts").fetchone()[:] == ("blob", b"\x00\xffold-label")
    assert case.conn.execute("SELECT lock_status FROM Schedule WHERE version=2 AND op_id=?", (case.op_id,)).fetchone()[0] == "locked"


def test_one_key_cannot_change_intent_or_scenario(trial_case):
    case = trial_case
    first = saved_scenario(case)
    second = saved_scenario(case, {"base": first["base"]}, suffix="0002")
    token = preview(case, first)
    result = service(case.conn).adopt(first["scenario_ref"], token, KEY, INTENT)
    before = snapshot(case.conn)
    for ref, intent in ((first["scenario_ref"], dict(INTENT, reason="different")), (second["scenario_ref"], INTENT)):
        with pytest.raises(WorkbenchCommandRejected) as error:
            service(case.conn).adopt(ref, token, KEY, intent)
        assert error.value.code == "request_key_conflict"
    assert service(case.conn).lookup(first["scenario_ref"], KEY)["receipt_ref"] == result["receipt_ref"]
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).lookup(second["scenario_ref"], KEY)
    assert snapshot(case.conn) == before

