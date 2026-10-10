"""Real adoption reads reuse proven sources only inside one SQLite snapshot."""

import json
from collections import Counter

import pytest

from core.infrastructure import read_evidence
from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import canonical_json
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES, PlanReadScope
from core.services.batch.service import BatchService
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.plan import adoption_baseline, adoption_baseline_sources, projection
from core.services.workbench.plan.adoption_baseline_values import AdoptionBaselineUnavailable
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
from tests.workbench.plan_adoption_baseline_support import adopt_candidate, mutate_json
from tests.workbench.plan_read_support import make_api
from tests.workbench.run_candidate_support import corrupt_update
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


@pytest.fixture
def adopted_versions(trial_case):
    case = trial_case
    first = adopt_candidate(case, "reuse-first")
    BatchService(case.conn).update("B1", quantity=5)
    second = adopt_candidate(case, "reuse-second")
    return case, first, second


def _workspace(case, plan):
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        return reader.workspace(PlanReadScope(plan["plan_ref"]))


def _track_sources(monkeypatch):
    calls = []
    load = adoption_baseline_sources._candidate_source

    def observed(conn, audit):
        calls.append((audit["run_ref"], audit["candidate_ref"]))
        return load(conn, audit)

    monkeypatch.setattr(adoption_baseline_sources, "_candidate_source", observed)
    return calls


def test_full_workspace_keeps_two_version_quantities_and_exact_uncached_output(adopted_versions, monkeypatch):
    case, first, second = adopted_versions
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    data, state = _workspace(case, second)
    baseline = data["projections"]["baseline"]
    assert baseline["state"] == "available" and baseline["baseline_plan"]["plan_ref"] == first["plan_ref"]
    assert data["tasks"][0]["quantity"] == 5
    assert baseline["items"][0]["before"]["quantity"] == 3
    assert baseline["items"][0]["after"]["quantity"] == 5
    assert len(calls) == 2 and set(Counter(calls).values()) == {1}
    assert len(canonical_json(data).encode("utf-8")) <= MAX_PLAN_RESPONSE_BYTES
    with monkeypatch.context() as uncached:
        for module in (adoption_baseline_sources, adoption_baseline, read_evidence):
            uncached.setattr(module, "verified_read", lambda conn, key, load: load())
        old_data, old_state = _workspace(case, second)
    assert canonical_json(data) == canonical_json(old_data) and state == old_state
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_dashboard_has_one_complete_source_proof_and_frozen_quantity(adopted_versions, monkeypatch):
    case, _, second = adopted_versions
    BatchService(case.conn).update("B1", quantity=7)
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    data, _ = read_dashboard_analysis(case.conn, second["plan_ref"])
    assert len(calls) == 1
    assert data["tasks"][0]["quantity"] == data["tasks"][0]["batch_quantity"] == 5
    assert data["tasks"][0]["quantity_basis"] == "run_admission"
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_quantity_without_reuse_scope_still_verifies_source_once(adopted_versions, monkeypatch):
    case, _, second = adopted_versions
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    reader = WorkbenchPlanQueryService(case.conn)
    # This standalone reader has a transaction but intentionally no evidence
    # scope. It must use the facts returned with its proof, not reprove them.
    with reader.read_snapshot():
        quantities, reason = projection._adopted_quantities(case.conn, second["plan_ref"])
    assert reason is None and quantities[case.op_id]["quantity"] == 5
    assert len(calls) == 1
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_caller_version_and_history_cannot_reuse_another_adoption(adopted_versions):
    case, first, second = adopted_versions
    reader = WorkbenchPlanQueryService(case.conn)
    history = WorkbenchPlanBaselineRepository(case.conn).get_history_result_summary(second["version"])
    before = snapshot(case.conn)
    with reader.read_snapshot(), read_evidence_scope(case.conn):
        assert projection.read_adopted_source(case.conn, second["plan_ref"]) is not None
        with pytest.raises(AdoptionBaselineUnavailable):
            adoption_baseline.read_adoption_baseline(case.conn, plan_ref=second["plan_ref"],
                version=first["version"], history=history, facts={})
        changed = dict(history)
        audit = json.loads(changed["result_summary"])
        audit["proof"]["candidate_hash"] = "0" * 64
        changed["result_summary"] = json.dumps(audit)
        with pytest.raises(AdoptionBaselineUnavailable):
            adoption_baseline.read_adoption_baseline(case.conn, plan_ref=second["plan_ref"],
                version=second["version"], history=changed, facts={})
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("fault", ["capture", "receipt", "arrangement"])
def test_new_request_rechecks_broken_source_and_rejects_old_snapshot(adopted_versions, fault):
    case, _, second = adopted_versions
    api = make_api(case.path)
    path = "/" + second["plan_ref"] + "/workspace"
    original = api.read(path)
    if fault == "capture":
        run_ref = case.conn.execute("SELECT run_ref FROM WorkbenchRunJobs ORDER BY accepted_at DESC, rowid DESC LIMIT 1").fetchone()[0]
        corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET facts_hash=? WHERE run_ref=?", ("0" * 64, run_ref))
    elif fault == "receipt":
        audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)).fetchone()[0])
        mutate_json(case.conn, "WorkbenchCommandReceipts", "outcome_json",
                    lambda value: value["data"]["official_plan"].update(plan_ref="f" * 48),
                    "request_key=?", (audit["request_key"],))
    else:
        corrupt_update(case.conn, "Schedule", "UPDATE Schedule SET end_time='2026-09-09T15:59:00' WHERE version=?", (second["version"],))
    before, changes = snapshot(case.conn), case.conn.total_changes
    fresh = api.read(path)["data"]
    assert fresh["tasks"][0]["quantity"] is None
    assert fresh["tasks"][0]["quantity_reason"] == "plan_target_unavailable"
    assert fresh["projections"]["baseline"]["state"] == "unavailable"
    response = api.get(path, snapshot_ref=original["meta"]["snapshot_ref"])
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_original_baseline_is_still_checked_independently(adopted_versions):
    case, first, second = adopted_versions
    corrupt_update(case.conn, "Schedule", "UPDATE Schedule SET end_time='2026-09-09T15:59:00' WHERE version=?", (first["version"],))
    before = snapshot(case.conn)
    data, _ = _workspace(case, second)
    assert data["tasks"][0]["quantity"] == 5
    assert data["projections"]["baseline"]["state"] == "unavailable"
    assert data["projections"]["baseline"]["reason_code"] == "adoption_baseline_drift"
    assert snapshot(case.conn) == before


def test_oversized_capture_keeps_original_64_mib_rejection(adopted_versions):
    case, _, second = adopted_versions
    audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)).fetchone()[0])
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET facts_json=? WHERE run_ref=?",
                   ("{}" + " " * (64 * 1024 * 1024), audit["run_ref"]))
    changes = case.conn.total_changes
    response = make_api(case.path).get("/" + second["plan_ref"] + "/workspace")
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "candidate_capacity_exceeded"
    assert case.conn.total_changes == changes
