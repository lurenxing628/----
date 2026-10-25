"""Claim retries reuse verified admission while checking each fresh snapshot."""

import pytest

from core.services.workbench.run.worker_claim import (
    capture_claim_retry_state,
    claim_run,
    require_retryable_claim,
)
from tests.workbench.run_candidate_support import corrupt_update
from tests.workbench.run_jobs_support import job_case as job_case  # noqa: F401


def test_claim_retry_reads_one_admission_receipt_per_snapshot(job_case):
    case = job_case
    run_ref = case.accept()["run_ref"]
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        original = capture_claim_retry_state(case.conn, run_ref)
        require_retryable_claim(case.conn, original)
        row, existing = claim_run(case.conn, run_ref, lambda: "2026-09-10T12:00:00", original)
    finally:
        case.conn.set_trace_callback(None)
    reads = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")
             and "FROM WORKBENCHCOMMANDRECEIPTS" in sql.upper()]
    assert len(reads) == 3
    assert original["admission"]["request_key"] == original["job"]["request_key"]
    assert row["state"] == "running" and existing is None


def test_claim_retry_rejects_changed_receipt_even_when_outcome_is_equivalent(job_case):
    case = job_case
    run_ref = case.accept()["run_ref"]
    original = capture_claim_retry_state(case.conn, run_ref)
    receipt = original["admission"]
    corrupt_update(case.conn, "WorkbenchCommandReceipts",
        "UPDATE WorkbenchCommandReceipts SET outcome_json=? WHERE request_key=?",
        (receipt["outcome_json"] + " ", receipt["request_key"]))
    changes = case.conn.total_changes
    with pytest.raises(RuntimeError, match="Run claim admission changed"):
        require_retryable_claim(case.conn, original)
    assert case.conn.execute("SELECT state FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()[0] == "queued"
    assert case.conn.total_changes == changes
