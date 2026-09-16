"""Durable admission, real candidates, replay, and original-library preservation."""

import json

import pytest

from core.infrastructure.logging import OperationLogger
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import connection, service  # noqa: F401
from tests.workbench.run_jobs_support import job_case as _job_case


def test_accept_and_real_candidate_result_preserve_original_database(job_case):
    case = job_case
    before = capture_run_facts(case.conn)
    accepted = case.accept()
    assert accepted["result"] == "accepted"
    assert accepted["data"]["state"] == "queued"
    assert capture_run_facts(case.conn) == before
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    assert result["result_persisted"] is True
    assert result["progress"] is None
    assert result["plans"] == [] and result["plan_catalog_connected"] is False
    assert len(result["candidates"]) == 4
    assert capture_run_facts(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 4
    for row in case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates"):
        artifact = json.loads(row[0])
        assert len(artifact["results"]) == len(artifact["validated_payload"]["schedule_rows"]) == 1
    with connection(case.path) as reopened:
        assert service(reopened).get(accepted["run_ref"]) == result
        assert service(reopened).lookup("run-request-00000001") == result


def test_replay_after_token_expiry_does_not_compute_or_reauthorize(job_case):
    case = job_case
    ref, token = case.intent()
    first = service(case.conn).accept(ref, token, "run-request-00000001")
    second = service(case.conn, enabled=False).accept(ref, None, "run-request-00000001")
    assert second["replayed"] is True
    assert second["receipt_ref"] == first["receipt_ref"]
    assert second["run_ref"] == first["run_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
    with pytest.raises(WorkbenchCommandRejected) as conflict:
        service(case.conn).accept("another-input-ref", token, "run-request-00000001")
    assert conflict.value.code == "request_key_conflict"


@pytest.mark.parametrize("token", [None, "", "not-issued"])
def test_preflight_is_not_run_authorization(job_case, token):
    case = job_case
    ref = case.preflight()
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_disabled_preview_and_accept_are_closed(job_case):
    ref, token = job_case.intent()
    disabled = service(job_case.conn, enabled=False)
    context = disabled.preview(ref)["write_context"]
    assert context["write_token"] is None
    assert context["capabilities"]["scheduling.run"] is False
    with pytest.raises(WorkbenchCommandRejected) as error:
        disabled.accept(ref, token, "run-request-00000001")
    assert error.value.code == "run_worker_not_connected"


def test_preflight_fact_drift_rejected_before_any_admission(job_case):
    case = job_case
    ref, token = case.intent()
    case.conn.execute("UPDATE Machines SET name='changed unselected display fact'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert error.value.code == "snapshot_stale"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_post_acceptance_fact_drift_records_failure_without_candidates(job_case):
    case = job_case
    accepted = case.accept()
    case.conn.execute("UPDATE Machines SET name='changed after accept'")
    case.conn.commit()
    before = capture_run_facts(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert error.value.code == "snapshot_stale"
    result = service(case.conn).get(accepted["run_ref"])
    assert result["state"] == "failed" and result["result_persisted"] is False
    assert capture_run_facts(case.conn) == before


def test_existing_official_history_and_legacy_candidates_are_preserved(job_case):
    case = job_case
    case.plan(1, [case.op_id])
    candidate = case.conn.execute("""INSERT INTO ScheduleCandidate
        (version,candidate_key,candidate_label,candidate_kind,status,detail_saved)
        VALUES (1,'legacy-preserved','Existing candidate','baseline','completed','yes')""").lastrowid
    case.conn.execute("""INSERT INTO ScheduleCandidateRows
        (version,candidate_id,op_id,machine_id,operator_id,start_time,end_time)
        VALUES (1,?,?,'M1','O1','2026-09-09 08:00:00','2026-09-09 08:45:00')""", (candidate, case.op_id))
    case.conn.commit()
    before = capture_run_facts(case.conn)
    accepted = case.accept()
    stored = case.conn.execute("SELECT baseline_json FROM WorkbenchRunJobs").fetchone()[0]
    baseline = json.loads(stored)
    assert baseline["plan_ref"] == case.plan_ref(1) and baseline["version"] == 1 and len(baseline["rows"]) == 1
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    assert capture_run_facts(case.conn) == before


def test_actual_excluded_batch_produces_persisted_partial_result(job_case):
    case = job_case
    case.batch("B2")
    case.operation("B2")
    case.conn.execute("UPDATE Batches SET ready_status='no' WHERE batch_id='B2'")
    case.conn.commit()
    before = capture_run_facts(case.conn)
    accepted = case.accept(settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "partial" and result["result_persisted"] is True
    assert all(row["task_count"] == 1 for row in result["candidates"])
    payload = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts").fetchone()[0])
    assert any(row["status"] == "skipped" for row in payload["dispositions"])
    assert capture_run_facts(case.conn) == before


def test_audit_writes_before_compute_and_before_persist_preserve_run(job_case, monkeypatch):
    from core.services.workbench import run_worker

    case = job_case
    accepted = case.accept()
    captured = tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone())
    assert OperationLogger(case.conn).info("plugins", "load", detail={"startup": True})
    real_compute = run_worker.compute_candidate_run

    def compute_with_audit(*args, **kwargs):
        result = real_compute(*args, **kwargs)
        assert OperationLogger(case.conn).info("system", "backup", detail={"complete": True})
        return result

    monkeypatch.setattr(run_worker, "compute_candidate_run", compute_with_audit)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"] is True
    assert tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone()) == captured
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action IN ('load','backup')").fetchone()[0] == 2
