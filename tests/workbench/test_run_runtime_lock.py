"""Ownership must be read from the exact current launcher and DB locks."""

import os
from contextlib import closing
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import new_run_ref
from core.services.scheduler import schedule_service
from core.services.workbench.run_jobs import WorkbenchRunService
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import install  # noqa: F401
from tests.workbench.run_runtime_support import owned_case as _owned_case
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime


def test_no_claim_disables_without_opening_or_creating_database(tmp_path):
    app = Flask(__name__)
    path = tmp_path / "absent.sqlite"
    app.config.update(DATABASE_PATH=str(path), WORKBENCH_RUN_JOBS_ENABLED=True)
    runtime = install_workbench_run_runtime(app)
    assert not path.exists()
    assert not runtime.ready and app.config["WORKBENCH_RUN_JOBS_ENABLED"] is False
    assert "workbench_run_dispatcher" not in app.extensions
    assert runtime.status["reason"] == "runtime_lock_not_supplied"
    assert runtime.shutdown()


@pytest.mark.parametrize("field,value", [("pid", 123456789), ("db_path", "/wrong/database"),
                                        ("exe_path", "/wrong/python"), ("owner", "different-owner")])
def test_current_db_lock_payload_must_match_all_identity_fields(owned_case, field, value):
    case = owned_case
    path = Path(db_scope_lock_path(str(case.path)))
    original = path.read_text(encoding="utf-8")
    lines = [field + "=" + str(value) if line.startswith(field + "=") else line
             for line in original.splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
        assert not runtime.ready and "owner_mismatch" in runtime.status["reason"]
        assert "workbench_run_dispatcher" not in case.app.extensions
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0
    finally:
        path.write_text(original, encoding="utf-8")


@pytest.mark.parametrize("claim", [True, {}, {"pid": os.getpid()}])
def test_boolean_guard_or_incomplete_claim_is_not_ownership(owned_case, claim):
    runtime = install_workbench_run_runtime(owned_case.app, runtime_lock=claim)
    assert not runtime.ready
    assert owned_case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] is False


def test_same_pid_other_database_and_same_basename_other_lock_do_not_authorize(owned_case, tmp_path):
    case = owned_case
    target = tmp_path / "other" / case.path.name
    target.parent.mkdir()
    with closing(get_connection(str(target))) as conn:
        case.conn.backup(conn)
    case.app.config["DATABASE_PATH"] = str(target)
    runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert not runtime.ready
    assert "owner_mismatch" in runtime.status["reason"]
    assert not Path(db_scope_lock_path(str(target))).exists()


def test_same_live_app_idempotent_second_app_rejected_and_closed_not_reused(owned_case):
    case = owned_case
    runtime = install(case)
    assert install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload) is runtime
    other = Flask("second-runtime-app")
    other.config["DATABASE_PATH"] = str(case.path)
    with pytest.raises(RuntimeError, match="already has"):
        install_workbench_run_runtime(other, runtime_lock=case.lock_payload)
    assert "workbench_run_dispatcher" not in other.extensions
    assert runtime.ready
    assert runtime.shutdown()
    with pytest.raises(RuntimeError, match="already closed"):
        install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    replacement = install_workbench_run_runtime(other, runtime_lock=case.lock_payload)
    try:
        assert replacement is not runtime and replacement.ready
    finally:
        assert replacement.shutdown()


def test_independent_actual_locks_allow_two_databases_same_process(owned_case, tmp_path):
    case = owned_case
    first = install(case)
    path = tmp_path / "independent.sqlite"
    with closing(get_connection(str(path))) as conn:
        case.conn.backup(conn)
    runtime_dir = str(tmp_path / "independent-launcher")
    claim = acquire_runtime_lock(runtime_dir, db_path=str(path))
    app = Flask("independent-runtime-app")
    app.config["DATABASE_PATH"] = str(path)
    second = install_workbench_run_runtime(app, runtime_lock=claim)
    try:
        assert first.ready and second.ready and first is not second
        assert first._thread is not second._thread
        assert first.shutdown() and second.ready
    finally:
        assert second.shutdown()
        release_runtime_lock(runtime_dir, db_path=str(path))


def test_debug_reloader_parent_never_starts_worker_even_with_real_lock(owned_case, monkeypatch):
    case = owned_case
    case.app.config["DEBUG"] = True
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert not runtime.ready and runtime._thread is None
    assert runtime.status["reason"] == "debug_reloader_parent"


def test_empty_v26_ensure_schema_database_recovers_and_enables(db_path, tmp_path):
    app = Flask("empty-v26-runtime")
    app.config["DATABASE_PATH"] = db_path
    runtime_dir = str(tmp_path / "empty-launcher")
    claim = acquire_runtime_lock(runtime_dir, db_path=db_path)
    runtime = install_workbench_run_runtime(app, runtime_lock=claim)
    try:
        assert runtime.ready, runtime.status
        assert runtime.recovery == {"recovered": [], "pending": [], "scheduling_busy": False}
        with closing(get_connection(db_path)) as conn:
            assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0
    finally:
        assert runtime.shutdown()
        release_runtime_lock(runtime_dir, db_path=db_path)


def test_recovery_busy_never_opens_write_capability(owned_case):
    case = owned_case
    with schedule_service._RUN_SCHEDULE_LOCK:
        runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert not runtime.ready and runtime.status["reason"] == "recovery_scheduling_busy"
    assert "workbench_run_dispatcher" not in case.app.extensions


def test_foreign_executor_not_inferred_dead_without_lock_proof(owned_case):
    case = owned_case
    ref = case.accept()["run_ref"]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        WorkbenchRunRepository(case.conn).claim(ref, new_run_ref(), "2000-01-01T00:00:00")
    result = WorkbenchRunService(case.conn).recover_unfinished_runs()
    assert result["pending"] == [ref]
    runtime = install_workbench_run_runtime(case.app)
    assert not runtime.ready
    row = WorkbenchRunService(case.conn).get(ref)
    assert row["state"] == "running" and row["stage"] == "awaiting_reconciliation"
    # Supplying the held, actual lock proves the old unmanaged owner is gone.
    runtime = install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert runtime.ready and runtime.recovery["recovered"] == [ref]
    assert WorkbenchRunService(case.conn).get(ref)["state"] == "interrupted"


def test_replacing_db_lock_with_identical_text_revokes_existing_proof(owned_case):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    path = Path(db_scope_lock_path(str(case.path)))
    original = path.read_text(encoding="utf-8")
    replacement = path.with_suffix(".replacement")
    replacement.write_text(original, encoding="utf-8")
    replacement.replace(path)
    with pytest.raises(RuntimeError, match="replaced"):
        runtime(ref)
    assert not runtime.ready
    assert WorkbenchRunService(case.conn).get(ref)["state"] == "queued"
