"""Failure injection at actual SQLite transaction boundaries; original rows survive."""

import json
import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain
from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_jobs_support import service


def test_receipt_write_failure_rolls_back_admission(job_case, monkeypatch):
    case = job_case
    ref, token = case.intent()
    before = all_rows(case.conn)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("accept receipt disk write failed")

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert all_rows(case.conn) == before
    assert not case.conn.in_transaction


@pytest.mark.parametrize("failure_stage", ["second_candidate", "result_receipt", "terminal_update"])
def test_result_second_write_and_receipt_failure_are_all_atomic(job_case, monkeypatch, failure_stage):
    case = job_case
    accepted = case.accept()
    before = capture_run_facts(case.conn)
    save = WorkbenchRunResultRepository.save
    finish = WorkbenchRunRepository.finish
    executed = []

    def broken_save(repo, run_ref, candidates):
        if failure_stage != "second_candidate":
            return save(repo, run_ref, candidates)
        save(repo, run_ref, candidates[:1])
        executed.append(repo.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0])
        raise sqlite3.OperationalError("second candidate write failed")

    def broken_finish(repo, run_ref, state, result, now):
        if failure_stage == "result_receipt":
            raise sqlite3.OperationalError("result receipt failed")
        if failure_stage == "terminal_update":
            finish(repo, run_ref, state, result, now)
            raise sqlite3.OperationalError("result transaction commit failed")
        return finish(repo, run_ref, state, result, now)

    monkeypatch.setattr(WorkbenchRunResultRepository, "save", broken_save)
    monkeypatch.setattr(WorkbenchRunRepository, "finish", broken_finish)
    with pytest.raises(WorkbenchCommandUncertain):
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert not case.conn.in_transaction
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0
    assert service(case.conn).get(accepted["run_ref"])["state"] == "running"
    assert capture_run_facts(case.conn) == before
    if failure_stage == "second_candidate":
        assert executed == [1]
    monkeypatch.undo()
    outcome = service(case.conn).recover_unfinished_runs()
    assert outcome["recovered"] == [accepted["run_ref"]]
    assert service(case.conn).get(accepted["run_ref"])["state"] == "interrupted"


def test_actual_zero_duration_candidate_is_visible_and_durable(job_case):
    case = job_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0")
    case.conn.commit()
    accepted = case.accept()
    before = capture_run_facts(case.conn)
    computed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    result = service(case.conn).get(accepted["run_ref"])
    assert result == computed
    assert result["state"] == "complete" and result["error"] is None
    assert result["result_persisted"] is True and result["candidates"]
    payloads = [json.loads(row[0]) for row in case.conn.execute("SELECT payload_json FROM WorkbenchRunCandidateTasks")]
    assert payloads and all(row["start_time"] == row["end_time"] for row in payloads)
    assert case.conn.execute("SELECT state FROM WorkbenchRunReceipts").fetchone()[0] == "complete"
    assert case.conn.execute("SELECT count(*) FROM Schedule").fetchone()[0] == 0
    assert capture_run_facts(case.conn) == before
