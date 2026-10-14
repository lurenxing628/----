"""Failure injection at actual SQLite transaction boundaries; original rows survive."""

import json
import sqlite3
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain, canonical_json
from core.services.workbench.facts.run_policy import public_run
from core.services.workbench.run.jobs_facts import capture_run_facts
from core.services.workbench.run.worker import WorkbenchRunWorker
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


@pytest.mark.parametrize("failure_stage", ["second_candidate"])
def test_result_second_write_and_receipt_failure_are_all_atomic(job_case, monkeypatch, failure_stage):
    case = job_case
    accepted = case.accept()
    captured_scope = accepted["data"]["scope_summary"]
    legacy_row = WorkbenchRunRepository(case.conn).get(accepted["run_ref"])
    legacy_facts = json.loads(legacy_row["facts_json"])
    legacy_facts["tables"].pop("ScheduleConfig")
    legacy_row["facts_json"] = canonical_json(legacy_facts)
    legacy_scope = public_run(case.conn, legacy_row)["scope_summary"]
    assert legacy_scope["objective"] is None and legacy_scope["objective_label"] is None
    assert {"field": "objective", "code": "not_recorded", "message": "排产时没有记下这一项。"} in legacy_scope["data_gaps"]
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
        WorkbenchRunWorker(case.conn, clock=lambda: datetime(2026, 9, 10, 12, 1, 0, 100000)).execute(accepted["run_ref"])
    assert not case.conn.in_transaction
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0
    running = service(case.conn).get(accepted["run_ref"])
    assert running["state"] == "running" and running["scope_summary"] == captured_scope
    assert capture_run_facts(case.conn) == before
    if failure_stage == "second_candidate":
        assert executed == [1]
    monkeypatch.undo()
    recovery = service(case.conn)
    recovery.clock = lambda: datetime(2026, 9, 10, 12, 1, 0, 123456)
    outcome = recovery.recover_unfinished_runs()
    assert outcome["recovered"] == [accepted["run_ref"]]
    interrupted = service(case.conn).get(accepted["run_ref"])
    assert interrupted["state"] == "interrupted" and interrupted["scope_summary"] == captured_scope
    assert interrupted["finished_at"] == "2026-09-10T12:01:00.123456"
