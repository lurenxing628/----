"""Pre-database startup admission and a permanently read-only recovery host."""

import os

from core.services.workbench.system_journal import assert_system_maintenance_ready

from .launcher_paths import _normalize_db_path_for_runtime
from .workbench_request_lifecycle import lookup_workbench_request_lifecycle
from .workbench_run_runtime_lock import RunRuntimeLockProof, RunRuntimeOwnershipError

RECOVERY = "workbench_system_restore_recovery"


def system_journal_directory(database_path):
    # Bind the default to the database, not an installation/log/backup directory.
    return os.path.realpath(database_path) + ".system-journal"


def prepare_system_restore_startup(app):
    """Run before templates, plugins, schema or any database connection."""
    directory = app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR")
    if directory is None:
        directory = os.environ.get("APS_SYSTEM_JOURNAL_DIR", system_journal_directory(app.config["DATABASE_PATH"]))
        app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = directory
    try:
        assert_system_maintenance_ready(app.config["DATABASE_PATH"], directory)
        gate = lookup_workbench_request_lifecycle(app.config["DATABASE_PATH"])
        if gate is not None and gate.status["state"] != "accepting":
            raise RuntimeError("Database lifecycle already stopped; restart the process")
    except Exception:
        app.logger.exception("System maintenance unconfirmed; starting journal-only recovery host")
        configure_system_restore_recovery(app)
        return True
    return False


def configure_system_restore_recovery(app):
    from .workbench_system_restore import make_workbench_system_restore_recovery_app

    app.config.update(WORKBENCH_RUN_JOBS_ENABLED=False, WORKBENCH_CANDIDATE_ADOPTION_ENABLED=False,
                      WORKBENCH_CALIBRATION_ADOPTION_ENABLED=False, WORKBENCH_RUN_RUNTIME_REASON=RECOVERY)
    app.extensions.pop("workbench_run_dispatcher", None)
    app.extensions.pop("workbench_system_restore_guard", None)
    app.extensions[RECOVERY] = True
    app.wsgi_app = make_workbench_system_restore_recovery_app(
        app.config["DATABASE_PATH"], app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"))


class RecoveryLockProof(RunRuntimeLockProof):
    def _require_database(self):
        # Recovery must work even when an interrupted copy left no DB file.
        # Both original lock files still undergo the full parent ownership proof.
        if self.db_path != os.path.normcase(os.path.realpath(self.db_path)):
            raise RunRuntimeOwnershipError("recovery_database_aliased")


class WorkbenchSystemRestoreRecoveryHost:
    def __init__(self, app, runtime_lock):
        self.app = app
        self.db_path = _normalize_db_path_for_runtime(app.config["DATABASE_PATH"])
        self.proof = RecoveryLockProof(self.db_path, runtime_lock)
        self.proof.verify()
        self.ready = False

    def shutdown(self, wait=True):
        # No worker or DB exists here. The owning server joins its HTTP handlers
        # before entrypoint/atexit may release the launcher's original locks.
        return True


def assert_exit_system_restore_ready(manager):
    app = getattr(manager, "_system_restore_app", None)
    directory = system_journal_directory(manager.db_path)
    if app is not None:
        directory = app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR")
        host = app.extensions.get("workbench_system_restore_host")
        if app.extensions.get(RECOVERY) or (host is not None and host.status["restart_required"]):
            raise RuntimeError("Restore requires process restart; exit backup must not open the database")
    assert_system_maintenance_ready(manager.db_path, directory)
