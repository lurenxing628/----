"""Full saved snapshot, real revalidation, original identity and no scope fallback."""

import pytest

from core.services.workbench.trial_adoption_validation import validate_trial_adoption
from tests.workbench.trial_adoption_support import preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import candidate, snapshot


@pytest.mark.parametrize("base", ["official", "candidate"])
def test_saved_arrangement_not_current_candidate_or_official(trial_case, base):
    case = trial_case
    saved = saved_scenario(case, candidate(case) if base == "candidate" else None)
    before = snapshot(case.conn)
    evidence = validate_trial_adoption(case.conn, saved["scenario_ref"])
    row = evidence.payload.schedule_rows[0]
    assert row.machine_id == "M2" and row.operator_id == "O2"
    assert row.start_time.isoformat() == saved["tasks"][0]["start"]
    assert evidence.scenario_ref == saved["scenario_ref"] and evidence.draft_ref == saved["draft_ref"]
    assert not hasattr(evidence, "candidate_ref")
    assert preview(case, saved)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("sql", [
    "UPDATE Machines SET status='maintenance' WHERE machine_id='M2'",
    "DELETE FROM OperatorMachine WHERE operator_id='O2'",
    "UPDATE BatchOperations SET unit_hours=2",
    "UPDATE Schedule SET lock_status='locked'",
    "INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_hours,efficiency,allow_normal,allow_urgent) "
    "VALUES ('O2','2026-09-09','workday','08:00',8,0.5,'yes','yes')",
])
def test_production_drift_blocks_without_mutation(trial_case, sql):
    case = trial_case
    saved = saved_scenario(case)
    case.conn.execute(sql)
    case.conn.commit()
    before = snapshot(case.conn)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before


def test_missing_batch_operations_not_filled_from_current_plan(trial_case):
    case = trial_case
    case.operation(seq=2)
    case.conn.commit()
    saved = saved_scenario(case)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["validation"]["issues"][0]["code"] == "scenario_scope_incomplete"


def test_disabled_preview_does_not_issue_token(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    result = service(case.conn, False).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False and result["write_context"]["write_token"] is None


def test_complete_single_piece_scope_has_read_only_adoption_evidence(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET quantity=1")
    case.conn.execute("UPDATE BatchOperations SET piece_id='single-piece'")
    case.conn.commit()
    case.plan(1, [case.op_id], end="2026-09-09T09:00:00")
    saved = saved_scenario(case, {"base": {"plan_ref": case.plan_ref(1)}}, changed=False)
    before = snapshot(case.conn)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is True, result
    assert result["validation"]["issues"] == []
    assert snapshot(case.conn) == before
