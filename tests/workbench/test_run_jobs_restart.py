"""Actual process loss and lost COMMIT acknowledgements against temporary SQLite files."""

import sqlite3
import subprocess
import sys

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain
from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_jobs_support import connection, service  # noqa: F401
from tests.workbench.test_run_jobs_support import job_case as _job_case


class LostCommitAcknowledgement(sqlite3.Connection):
    fail_when = None

    def commit(self):
        lost = False
        if self.fail_when == "accept":
            lost = self.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] > 0
        elif self.fail_when == "result":
            lost = self.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] > 0
        super().commit()
        if lost:
            self.fail_when = None
            raise sqlite3.OperationalError("COMMIT completed but acknowledgement was lost")


@pytest.mark.parametrize("stage", ["accept", "result"])
def test_lost_commit_acknowledgement_recovers_committed_result(job_case, stage):
    case = job_case
    ref, token = case.intent()
    conn = sqlite3.connect(str(case.path), factory=LostCommitAcknowledgement)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if stage == "accept":
            conn.fail_when = stage
            with pytest.raises(WorkbenchCommandUncertain):
                service(conn).accept(ref, token, "run-request-00000001")
            replay = service(case.conn).accept(ref, None, "run-request-00000001")
            assert replay["replayed"] and replay["data"]["state"] == "queued"
        else:
            accepted = service(case.conn).accept(ref, token, "run-request-00000001")
            conn.fail_when = stage
            with pytest.raises(WorkbenchCommandUncertain):
                WorkbenchRunWorker(conn).execute(accepted["run_ref"])
            state = service(case.conn).get(accepted["run_ref"])
            assert state["state"] == "complete" and state["result_persisted"]
            assert service(case.conn).recover_unfinished_runs()["recovered"] == []
            assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"]) == state
    finally:
        conn.close()


def test_process_exits_after_first_candidate_write_preserving_original_database(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    before = capture_run_facts(case.conn)
    script = """
import os, sqlite3, sys
from core.services.workbench.run_worker import WorkbenchRunWorker
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository
conn=sqlite3.connect(sys.argv[1]); conn.row_factory=sqlite3.Row
conn.execute('PRAGMA foreign_keys=ON')
save=WorkbenchRunResultRepository.save
def crash(repo, run_ref, candidates):
    save(repo, run_ref, candidates[:1])
    assert repo.conn.execute('SELECT COUNT(*) FROM WorkbenchRunCandidateTasks').fetchone()[0] == 1
    os._exit(23)
WorkbenchRunResultRepository.save=crash
WorkbenchRunWorker(conn).execute(sys.argv[2])
"""
    completed = subprocess.run([sys.executable, "-c", script, str(case.path), ref], capture_output=True, text=True, timeout=45)
    assert completed.returncode == 23, completed.stderr
    with connection(case.path) as restarted:
        assert capture_run_facts(restarted) == before
        assert restarted.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
        assert restarted.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0
        unknown = service(restarted).recover_unfinished_runs()
        assert unknown["pending"] == [ref]
        assert service(restarted).get(ref)["state"] == "running"
        # subprocess.wait has positively confirmed that this sole foreign owner exited.
        recovered = service(restarted).recover_unfinished_runs(executor_is_active=lambda owner: False)
        assert recovered["recovered"] == [ref]
        assert service(restarted).get(ref)["state"] == "interrupted"
