"""Neutral persistence keeps source identity and the enclosing transaction intact."""

import copy
import json

import pytest

from core.services.workbench.official_plan_persistence import persist_official_plan_in_tx
from core.services.workbench.run_candidate_adoption_validation import validate_adoption
from tests.workbench.test_run_candidate_adoption_support import assert_retained, candidate, snapshot
from tests.workbench.test_run_candidate_adoption_support import candidate_case as _case  # noqa: F401


def arguments(case):
    evidence = validate_adoption(case.conn, candidate(case))
    return {"prepared": evidence.prepared, "payload": evidence.payload, "baseline": evidence.baseline,
            "audit": {"action": "adopt_trial_scenario", "source": "workbench_trial_adoption",
                      "scenario_ref": "scenario-proof", "draft_ref": "draft-proof",
                      "request_key": "neutral-persistence-0001", "proof": evidence.snapshot,
                      "reason": "Test the shared writer, not scenario validation", "declared_operator": "Planner"},
            "application_operator": "Local test operator"}


def test_source_neutral_writer_does_not_invent_candidate_identity_or_own_commit(candidate_case):
    case = candidate_case
    values = arguments(case)
    audit = copy.deepcopy(values["audit"])
    before = snapshot(case.conn)
    case.conn.execute("BEGIN IMMEDIATE")
    result = persist_official_plan_in_tx(case.conn, **values)
    assert case.conn.in_transaction and values["audit"] == audit
    identity = result["official_plan"]
    assert result["row_count"] == 1 and identity["version"] == 1
    assert "source_run_ref" not in identity and "candidate_ref" not in identity
    history = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory").fetchone()[0])
    event = case.conn.execute("SELECT action,detail FROM OperationLogs").fetchone()
    details = json.loads(event["detail"])
    for recorded in (history, details):
        assert recorded["source"] == "workbench_trial_adoption"
        assert recorded["scenario_ref"] == "scenario-proof" and recorded["draft_ref"] == "draft-proof"
        assert "candidate_ref" not in recorded and "run_ref" not in recorded
        assert recorded["application_operator"] == "Local test operator"
    assert event["action"] == "adopt_trial_scenario" and details["plan_ref"] == identity["plan_ref"]
    assert_retained(before, snapshot(case.conn))
    case.conn.rollback()
    assert snapshot(case.conn) == before


def test_shared_writer_requires_callers_transaction_before_any_write(candidate_case):
    case = candidate_case
    values = arguments(case)
    before = snapshot(case.conn)
    with pytest.raises(RuntimeError, match="caller's write transaction"):
        persist_official_plan_in_tx(case.conn, **values)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("field", ["action", "source"])
def test_missing_audit_routing_never_allocates_a_formal_version(candidate_case, field):
    case = candidate_case
    values = arguments(case)
    values["audit"][field] = ""
    before = snapshot(case.conn)
    case.conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError, match="action and source"):
        persist_official_plan_in_tx(case.conn, **values)
    assert snapshot(case.conn) == before
    case.conn.rollback()
