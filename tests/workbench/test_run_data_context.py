"""Restore-aware run lookup uses durable evidence without retrying or rewriting work."""

import re
from contextlib import closing
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_data_context import RunDataContext
from core.services.workbench.system_journal import SystemMaintenanceJournal, file_fingerprint
from tests.workbench.run_jobs_support import connection
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_run_jobs_api import BASE, intent
from tests.workbench.test_run_jobs_api import jobs_api as _jobs_api  # noqa: F401

KEY = "restore-context-run-request-000001"


@pytest.fixture
def context_case(job_case, tmp_path, monkeypatch):
    journal_dir = tmp_path / "run-context-journal"
    backup_dir = tmp_path / "run-context-backups"
    journal_dir.mkdir()
    backup_dir.mkdir()
    ticks = count()

    class JournalClock:
        @staticmethod
        def now():
            return datetime(2026, 9, 15, 12) + timedelta(seconds=next(ticks))

    monkeypatch.setattr("core.services.workbench.system_journal.datetime", JournalClock)
    job_case.app.config.update(WORKBENCH_SYSTEM_JOURNAL_DIR=str(journal_dir), BACKUP_DIR=str(backup_dir))
    journal = SystemMaintenanceJournal(str(journal_dir), str(job_case.path))
    context = RunDataContext(job_case.conn, journal_dir=str(journal_dir), backup_dir=str(backup_dir))
    return SimpleNamespace(job=job_case, journal=journal, context=context, backups=backup_dir)


def record_restore(case, *, key="restore-context-maintenance-000001", state="succeeded",
                   code="verified", protection=None, previous_context=None):
    row, _ = case.journal.begin(key, "restore", {})
    values = {"code": code, "protection": protection}
    if previous_context is not None:
        values["data_context_before"] = previous_context
    return case.journal.record(row, state, **values)


def snapshot(conn, path):
    with closing(connection(path)) as destination:
        conn.backup(destination)
    return {"filename": path.name, "sha256": file_fingerprint(str(path))}


def restored_admission(case):
    """Actually replace only a disposable DB, preserving the immutable-ledger schema."""
    baseline = case.backups / "before-run.db"
    snapshot(case.job.conn, baseline)
    accepted = case.job.accept(key=KEY)
    protection = snapshot(case.job.conn, case.backups / "aps_backup_protected_before_restore.db")
    with closing(connection(baseline)) as original:
        original.backup(case.job.conn)
    assert case.job.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0
    return protection, accepted


def test_context_stable_across_ordinary_reopen_and_read_only(context_case):
    case = context_case
    changes = case.job.conn.total_changes
    initial = case.context.ref()
    assert re.fullmatch(r"[a-f0-9]{64}", initial)
    with closing(connection(case.job.path)) as reopened:
        again = RunDataContext(reopened, journal_dir=case.journal.directory, backup_dir=str(case.backups))
        assert again.ref() == initial
    assert case.context.resolve_missing(KEY) == "unresolved"
    assert case.context.resolve_missing(KEY, previous_context="f" * 64) == "unresolved"
    assert case.job.conn.total_changes == changes
    assert list(case.backups.iterdir()) == []
    assert case.journal.records() == []


@pytest.mark.parametrize("state,code", [("failed", "backup_missing"),
                                       ("rolled_back", "restore_failed_rolled_back")])
def test_unsuccessful_restore_does_not_rotate_or_resolve(context_case, state, code):
    case = context_case
    before = case.context.ref()
    record_restore(case, state=state, code=code)
    assert case.context.ref() == before
    assert case.context.resolve_missing(KEY, previous_context=before) == "unresolved"


def test_successful_restore_resolves_only_known_old_context(context_case):
    case = context_case
    initial = case.context.ref()
    record_restore(case, previous_context=initial)
    current = case.context.ref()
    assert current != initial
    assert case.context.resolve_missing(KEY, previous_context=initial) == "context_replaced"
    assert case.context.resolve_missing(KEY, previous_context=current) == "unresolved"
    assert case.context.resolve_missing(KEY, previous_context="e" * 64) == "unresolved"
    assert case.context.resolve_missing(KEY) == "unresolved"
    record_restore(case, key="restore-context-maintenance-000002", previous_context=current)
    assert case.context.ref() not in (initial, current)
    assert case.context.resolve_missing(KEY, previous_context=initial) == "context_replaced"
    assert case.context.resolve_missing(KEY, previous_context=current) == "context_replaced"


def test_pending_restore_rejects_context_and_resolution(context_case):
    case = context_case
    case.journal.begin("restore-context-maintenance-000001", "restore", {})
    for operation in (case.context.ref, lambda: case.context.resolve_missing(KEY)):
        with pytest.raises(WorkbenchCommandRejected) as error:
            operation()
        assert error.value.code == "maintenance_active"


def test_legacy_request_requires_exact_registered_protection_evidence(context_case):
    case = context_case
    protection, accepted = restored_admission(case)
    record_restore(case, protection=protection)
    database_before = tuple(case.job.conn.iterdump())
    journal_before = {path.name: path.read_bytes() for path in Path(case.journal.directory).iterdir()}
    changes = case.job.conn.total_changes
    assert case.context.resolve_missing(KEY) == "context_replaced"
    assert case.context.resolve_missing(KEY + "-unknown") == "unresolved"
    assert tuple(case.job.conn.iterdump()) == database_before
    assert case.job.conn.total_changes == changes
    assert file_fingerprint(str(case.backups / protection["filename"])) == protection["sha256"]
    assert {path.name: path.read_bytes() for path in Path(case.journal.directory).iterdir()} == journal_before
    with closing(connection(case.backups / protection["filename"])) as saved:
        assert saved.execute("SELECT run_ref FROM WorkbenchRunJobs WHERE request_key=?", (KEY,)).fetchone()[0] == accepted["run_ref"]


@pytest.mark.parametrize("damage", ["unregistered", "missing", "changed", "schema_missing"])
def test_legacy_request_without_verified_protection_remains_unresolved(context_case, damage):
    case = context_case
    protection, _ = restored_admission(case)
    path = case.backups / protection["filename"]
    if damage == "missing":
        path.unlink()
    elif damage == "changed":
        with closing(connection(path)) as saved:
            saved.execute("UPDATE Machines SET name='changed after protection registration'")
            saved.commit()
    elif damage == "schema_missing":
        path.unlink()
        with closing(connection(path)) as saved:
            saved.execute("CREATE TABLE unrelated(value TEXT)")
            saved.commit()
        protection["sha256"] = file_fingerprint(str(path))
    record_restore(case, protection=None if damage == "unregistered" else protection)
    assert case.context.resolve_missing(KEY) == "unresolved"


def test_legacy_request_does_not_search_older_or_unregistered_backup(context_case):
    case = context_case
    protection, _ = restored_admission(case)
    record_restore(case, protection=protection)
    newest = snapshot(case.job.conn, case.backups / "aps_backup_newest_before_restore.db")
    record_restore(case, key="restore-context-maintenance-000002", protection=newest)
    assert case.context.resolve_missing(KEY) == "unresolved"


def test_old_preview_is_rejected_after_completed_restore_without_dispatch(jobs_api, context_case):
    client, job, calls = jobs_api
    case = context_case
    body = intent(client, job)
    old = case.context.ref()
    record_restore(case, previous_context=old)
    response = client.post(BASE + "/runs", json=body)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "stale_write"
    assert response.get_json()["committed"] is False
    assert calls == []
    assert job.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_existing_current_run_wins_over_old_context_without_redispatch(jobs_api, context_case):
    client, job, calls = jobs_api
    case = context_case
    body = intent(client, job)
    old = case.context.ref()
    accepted = client.post(BASE + "/runs", json=body)
    assert accepted.status_code == 202
    assert accepted.get_json()["data_context_ref"] == old
    run_ref = accepted.get_json()["run_ref"]
    record_restore(case, previous_context=old)
    response = client.get(BASE + "/requests/" + body["request_key"], query_string={"data_context_ref": old})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["found"] is True and data["run"]["run_ref"] == run_ref
    assert data["data_context_ref"] == case.context.ref()
    assert data["resolution"] != "context_replaced"
    assert calls == [run_ref]


def test_legacy_lookup_exposes_restoration_resolution_without_writes_or_dispatch(jobs_api, context_case):
    client, job, calls = jobs_api
    case = context_case
    protection, _ = restored_admission(case)
    record_restore(case, protection=protection)
    changes = job.conn.total_changes
    for key, resolution in ((KEY, "context_replaced"), (KEY + "-unknown", "unresolved")):
        response = client.get(BASE + "/requests/" + key)
        assert response.status_code == 200
        assert response.get_json()["data"] == {"found": False, "run": None,
            "data_context_ref": case.context.ref(), "resolution": resolution}
    assert job.conn.total_changes == changes
    assert calls == []


@pytest.mark.parametrize("value", ["", "invalid", "A" * 64, "a" * 63, "a" * 65])
def test_lookup_rejects_malformed_context_without_dispatch(jobs_api, context_case, value):
    client, job, calls = jobs_api
    response = client.get(BASE + "/requests/" + KEY, query_string={"data_context_ref": value})
    assert response.status_code == 400
    assert calls == []


def test_preview_exposes_current_data_context(jobs_api, context_case):
    client, job, _ = jobs_api
    ref = job.preflight()
    response = client.post(BASE + "/runs/preview", json={"input_ref": ref})
    assert response.status_code == 200
    assert response.get_json()["data"]["data_context_ref"] == context_case.context.ref()
