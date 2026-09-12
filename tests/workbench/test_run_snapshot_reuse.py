"""One continuous read snapshot saves a scan; independent inputs stay checked."""

import json
from dataclasses import replace

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench import preflight_facts, run_compute, run_worker
from core.services.workbench.run_input import prepare_candidate_run_input
from tests.workbench.final_capacity_observation import observe_worker
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401


def _count_fingerprints(monkeypatch):
    calls = []
    original = preflight_facts.full_facts_fingerprint

    def fingerprint(conn):
        assert conn.in_transaction
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        result = original(conn)
        calls.append(result)
        return result

    monkeypatch.setattr(preflight_facts, "full_facts_fingerprint", fingerprint)
    monkeypatch.setattr(run_compute, "full_facts_fingerprint", fingerprint)
    return calls


def _outcomes(result):
    comparison = result.orchestration.candidate_comparison
    return [(plan.candidate_key, plan.status, plan.results, plan.score, plan.metrics)
            for plan in comparison.candidates]


def test_combined_run_reads_one_full_fingerprint_and_matches_independent_run(run_case, monkeypatch):
    case = run_case
    # Unequal chains plus an unselected batch exercise complete input scope.
    case.operation(seq=2, setup_hours=0.5)
    case.batch("B2")
    case.operation(batch="B2", unit_hours=0.75)
    case.conn.commit()
    settings, projections = case.settings(), case.projections("B1")
    calls = _count_fingerprints(monkeypatch)
    combined = unchanged(case, lambda: run_compute.compute_candidate_run(case.conn, settings, projections))
    assert calls == [combined.schedule_input.facts_fingerprint]
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, settings, projections))
    independent = unchanged(case, lambda: run_compute.compute_prepared_candidate_run(case.conn, prepared))
    assert len(calls) == 3 and len(set(calls)) == 1
    assert combined.candidate_payloads == independent.candidate_payloads
    assert combined.dispositions == independent.dispositions
    assert combined.state == independent.state
    assert _outcomes(combined) == _outcomes(independent)


@pytest.mark.parametrize("sql", [
    "UPDATE BatchOperations SET unit_hours=0.5",
    "UPDATE Machines SET name='changed machine'",
    "UPDATE ScheduleConfig SET config_value='no' WHERE config_key='ortools_enabled'",
    "CREATE TABLE UnselectedFacts (value TEXT)",
    "UPDATE ArchivedInput SET value='changed outside selected scope'",
])
def test_independent_input_always_rechecks_all_fact_tables(run_case, sql):
    case = run_case
    case.conn.execute("CREATE TABLE ArchivedInput (value TEXT)")
    case.conn.execute("INSERT INTO ArchivedInput VALUES ('original')")
    case.conn.commit()
    if sql.startswith("UPDATE ScheduleConfig"):
        case.config(ortools_enabled="yes")
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    case.conn.execute(sql)
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: run_compute.compute_prepared_candidate_run(case.conn, prepared))
    assert error.value.reason == "candidate_input_stale"


def test_combined_result_input_has_no_reusable_freshness_bypass(run_case):
    case = run_case
    combined = run_compute.compute_candidate_run(case.conn, case.settings(), case.projections())
    case.conn.execute("UPDATE Machines SET name='changed after combined run'")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: run_compute.compute_prepared_candidate_run(case.conn, combined.schedule_input))
    assert error.value.reason == "candidate_input_stale"


def test_combined_preparation_and_computation_share_one_outer_transaction(run_case):
    case = run_case
    settings, projections = case.settings(), case.projections()
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        unchanged(case, lambda: run_compute.compute_candidate_run(case.conn, settings, projections))
    finally:
        case.conn.set_trace_callback(None)
    boundaries = [sql.strip().upper() for sql in statements
                  if sql.strip().upper() in ("BEGIN", "COMMIT", "ROLLBACK")]
    assert boundaries == ["BEGIN", "COMMIT"]
    assert not case.conn.in_transaction
    assert case.conn.execute("PRAGMA query_only").fetchone()[0] == 0


def test_combined_path_keeps_connection_identity_check(run_case, monkeypatch):
    case = run_case
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    wrong = replace(prepared, cal_svc=type("ForeignCalendar", (), {"conn": object()})())
    monkeypatch.setattr(run_compute, "prepare_candidate_run_input", lambda *args: wrong)
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: run_compute.compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "candidate_connection_mismatch"


@pytest.mark.parametrize("open_transaction", [False, True])
def test_private_continuation_rejects_missing_read_scope(run_case, open_transaction):
    case = run_case
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    if open_transaction:
        case.conn.execute("BEGIN")
    try:
        with pytest.raises(CandidateRunInputError) as error:
            unchanged(case, lambda: run_compute._compute_in_read_snapshot(case.conn, prepared, 0))
        assert error.value.reason == "candidate_read_snapshot_lost"
    finally:
        case.conn.rollback()


def test_worker_uses_one_fingerprint_and_keeps_prepare_engine_observation(job_case, monkeypatch, tmp_path):
    accepted = job_case.accept()
    calls = _count_fingerprints(monkeypatch)
    with observe_worker(tmp_path, profile=True):
        result = run_worker.WorkbenchRunWorker(job_case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    assert len(calls) == 1
    stages = [json.loads(line) for line in (tmp_path / "worker-stages.jsonl").read_text().splitlines()]
    by_stage = {item["stage"]: item for item in stages}
    assert {"prepare", "engine", "serialization", "persistence", "worker_total"} <= set(by_stage)
    assert all(item["completed"] and item["measurement_scope_version"] == 2 for item in stages)
    assert by_stage["prepare"]["ended_seconds"] <= by_stage["engine"]["started_seconds"]
    assert by_stage["engine"]["cprofile_enabled"]
    assert by_stage["engine"]["function"].endswith("._compute_in_read_snapshot")
    assert (tmp_path / "managed-engine.pstats").is_file()
