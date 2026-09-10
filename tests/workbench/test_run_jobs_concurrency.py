"""Independent SQLite connections exercise real admission and shared scheduler exclusion."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.infrastructure.backup import BackupManager
from core.infrastructure.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench import run_worker
from core.services.workbench.run_jobs_facts import capture_run_facts
from tests.workbench.test_run_jobs_support import connection, service  # noqa: F401
from tests.workbench.test_run_jobs_support import job_case as _job_case


def test_twelve_simultaneous_same_intents_commit_once(job_case):
    case = job_case
    ref, token = case.intent()
    start = threading.Barrier(12)

    def accept(_):
        conn = connection(case.path)
        try:
            with case.app.app_context():
                start.wait(timeout=10)
                return service(conn).accept(ref, token, "run-request-00000001")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(accept, range(12)))
    assert len({row["run_ref"] for row in results}) == len({row["receipt_ref"] for row in results}) == 1
    assert sum(not row["replayed"] for row in results) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE action='scheduling.run'").fetchone()[0] == 1


def test_different_request_keys_cannot_bypass_stale_preflight(job_case):
    case = job_case
    ref, token = case.intent()
    start = threading.Barrier(4)

    def accept(index):
        conn = connection(case.path)
        try:
            with case.app.app_context():
                start.wait(timeout=10)
                try:
                    return service(conn).accept(ref, token, f"run-distinct-{index:08d}")
                except WorkbenchCommandRejected as exc:
                    return {"code": exc.code}
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(accept, range(4)))
    assert sum(row.get("result") == "accepted" for row in results) == 1
    assert sum(row.get("code") == "snapshot_stale" for row in results) == 3


def test_two_workers_and_legacy_run_share_one_lock(job_case, monkeypatch):
    case = job_case
    ref = case.accept()["run_ref"]
    entered, release = threading.Event(), threading.Event()
    calls = []
    real_compute = run_worker.compute_prepared_candidate_run

    def delayed(conn, prepared):
        calls.append(ref)
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        entered.set()
        assert release.wait(timeout=15)
        return real_compute(conn, prepared)

    def execute():
        conn = connection(case.path)
        try:
            return run_worker.WorkbenchRunWorker(conn).execute(ref)
        finally:
            conn.close()

    monkeypatch.setattr(run_worker, "compute_prepared_candidate_run", delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(execute)
        try:
            assert entered.wait(timeout=15)
            with pytest.raises(WorkbenchCommandRejected) as busy:
                run_worker.WorkbenchRunWorker(case.conn).execute(ref)
            assert busy.value.code == "scheduling_busy"
            with pytest.raises(ValidationError, match="正在执行排产"):
                ScheduleService(case.conn).run_schedule(["B1"])
            for _ in range(5):
                assert service(case.conn).get(ref)["state"] == "running"
            assert service(case.conn).recover_unfinished_runs()["scheduling_busy"] is True
        finally:
            release.set()
        assert future.result(timeout=30)["state"] == "complete"
    again = run_worker.WorkbenchRunWorker(case.conn).execute(ref)
    assert again["state"] == "complete" and calls == [ref]


@pytest.mark.parametrize("journal_mode", ["WAL", "DELETE"])
def test_calculation_allows_other_writer_and_rejects_late_fact_drift(job_case, monkeypatch, journal_mode):
    case = job_case
    case.conn.execute("PRAGMA journal_mode=" + journal_mode)
    ref = case.accept()["run_ref"]
    compute = run_worker.compute_prepared_candidate_run
    changes = []

    def concurrent_write(conn, prepared):
        assert conn is not case.conn and not case.conn.in_transaction
        # Even a rollback-journal writer commits: the original DB has no pinned reader.
        with connection(case.path) as writer:
            writer.execute("UPDATE Machines SET name='changed during actual computation'")
            writer.commit()
        changes.append(True)
        return compute(conn, prepared)

    monkeypatch.setattr(run_worker, "compute_prepared_candidate_run", concurrent_write)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_worker.WorkbenchRunWorker(case.conn).execute(ref)
    assert error.value.code == "snapshot_stale" and changes == [True]
    assert service(case.conn).get(ref)["state"] == "failed"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
    assert case.conn.execute("SELECT name FROM Machines").fetchone()[0] == "changed during actual computation"


def test_actual_maintenance_backup_and_reads_respond_during_computation(job_case, monkeypatch, tmp_path):
    case = job_case
    case.conn.execute("PRAGMA journal_mode=DELETE")
    ref = case.accept()["run_ref"]
    compute = run_worker.compute_prepared_candidate_run
    backup_paths = []

    def maintenance_while_computing(snapshot, prepared):
        assert snapshot is not case.conn and not case.conn.in_transaction
        path = BackupManager(str(case.path), str(tmp_path / "maintenance-backups")).backup("running")
        backup_paths.append(path)
        with connection(path) as backup:
            assert service(backup).get(ref)["state"] == "running"
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert service(case.conn).get(ref)["state"] == "running"
        return compute(snapshot, prepared)

    monkeypatch.setattr(run_worker, "compute_prepared_candidate_run", maintenance_while_computing)
    result = run_worker.WorkbenchRunWorker(case.conn).execute(ref)
    assert result["state"] == "complete" and len(backup_paths) == 1


def test_new_runs_preserve_prior_candidates_and_history(job_case):
    case = job_case
    first = run_worker.WorkbenchRunWorker(case.conn).execute(case.accept()["run_ref"])
    rows = [tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchRunCandidateTasks ORDER BY row_ref")]
    facts = capture_run_facts(case.conn)
    second = run_worker.WorkbenchRunWorker(case.conn).execute(case.accept("run-request-00000002")["run_ref"])
    assert first["run_ref"] != second["run_ref"]
    assert service(case.conn).get(first["run_ref"]) == first
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 8
    saved = {tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchRunCandidateTasks")}
    assert set(rows) <= saved and capture_run_facts(case.conn) == facts
