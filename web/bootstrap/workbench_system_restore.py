"""HTTP restore host; never acquire/release launcher locks or restart a worker.

Integration contract (owned by factory/entrypoint, not this module):
* At startup, BEFORE the first DB open/migration/plugin/worker, call the external
  assert_system_maintenance_ready(database_path, journal_dir) hook. Check it
  before automatic exit backups too, not inside the restore's owned DB access.
* Install the real request lifecycle, then the real run runtime with the original
  launcher lock payload; install_workbench_system_restore_host(app, runtime=...)
  must run before serving HTTP. No bool callback constitutes host integration.
* After any accepted restore, restart the PROCESS, not just the browser or Flask
  app. Keep the original launcher locks until HTTP and worker shutdown prove done.
  Pending/unreadable journals must block startup and automatic exit backups.
* The outer WSGI result transport reads only the external journal. It cannot
  admit a business request, mount g.db, dispatch work, resume, or replay a write.
  Even /system/runtime/shutdown is blocked: the host must provide a server-side
  lifecycle stop, then join HTTP and worker barriers before releasing locks.
"""

import math
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import g, has_request_context

from core.infrastructure.backup import is_maintenance_window_active
from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler import schedule_service
from core.services.system.backup_restore import audit_backup_operation
from core.services.workbench.system_journal import SystemMaintenanceJournal

from .launcher_paths import _normalize_db_path_for_runtime
from .workbench_request_lifecycle import (
    WorkbenchRequestLifecycle,
    close_workbench_request_connection,
    lookup_workbench_request_lifecycle,
    track_workbench_request_connection,
)
from .workbench_request_lifecycle_state import current_frame
from .workbench_run_runtime import WorkbenchRunRuntime
from .workbench_run_runtime_lock import RunRuntimeLockProof
from .workbench_system_restore_status import install_restore_status_transport

EXTENSION = "workbench_system_restore_host"
GUARD = "workbench_system_restore_guard"


class WorkbenchSystemRestoreHost:
    def __init__(self, app, runtime):
        self.app, self.runtime = app, runtime
        self.db_path = _normalize_db_path_for_runtime(app.config["DATABASE_PATH"])
        self.journal = SystemMaintenanceJournal(app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"), self.db_path)
        self.gate = app.extensions.get("workbench_request_lifecycle")
        self._lock = threading.RLock()
        self._state, self._request_key = "ready", None
        self.timeout = float(app.config.get("WORKBENCH_SYSTEM_RESTORE_DRAIN_TIMEOUT", 30))
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("Restore drain timeout must be finite and positive")
        self.verify()
        if not runtime.ready or self.gate.status["state"] != "accepting":
            raise RuntimeError("Restore requires a ready managed runtime and accepting HTTP lifecycle")
        self.journal.assert_ready()

    def __call__(self):
        """Capability presentation only; execution requires this concrete controller."""
        return self.status["operations_available"]

    @property
    def status(self):
        with self._lock:
            journal_ready = False
            if self._state == "ready":
                try:
                    self.verify()
                    journal_ready = self._journal_ready()
                except Exception:
                    self.app.logger.exception("Restore journal/ownership became unconfirmed; closing admission")
                    self._stop_unconfirmed(self._request_key)
            return {"state": self._state, "request_key": self._request_key,
                    "restart_required": self._state != "ready", "automatic_resume": False,
                    "operations_available": (self._state == "ready" and journal_ready and self.runtime.ready
                                             and self.gate.status["state"] == "accepting"),
                    "result_source": "external_maintenance_journal",
                    "references": "reload_from_database_after_process_restart",
                    "receipt_policy": "file_results_from_journal_database_receipts_from_current_database"}

    def _journal_ready(self):
        pending = self.journal.pending()
        if not pending:
            return True
        # A live non-restore file command owns its maintenance window until the
        # terminal journal write. It is busy, not an interrupted restore host.
        if (all(row["action"] in ("create", "delete") and row["state"] in ("accepted", "checking")
                for row in pending)
                and is_maintenance_window_active(self.db_path, logger=self.app.logger) is True):
            return False
        self.journal.assert_ready()
        return True

    def _set_state(self, state, request_key):
        with self._lock:
            self._state, self._request_key = state, request_key

    def verify(self):
        app, runtime, gate = self.app, self.runtime, self.gate
        if (_normalize_db_path_for_runtime(app.config.get("DATABASE_PATH")) != self.db_path
                or app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR") != self.journal.directory
                or not isinstance(gate, WorkbenchRequestLifecycle)
                or gate is not lookup_workbench_request_lifecycle(self.db_path)
                or gate is not app.extensions.get("workbench_request_lifecycle")
                or not isinstance(runtime, WorkbenchRunRuntime)
                or runtime is not app.extensions.get("workbench_run_runtime")
                or runtime.app is not app or runtime.db_path != self.db_path
                or not isinstance(runtime.proof, RunRuntimeLockProof)):
            raise RuntimeError("Restore host ownership/configuration is missing or changed")
        runtime.proof.verify()

    def execute(self, service, *, request_key, intent, guard, audit, restore_runner):
        self.verify()
        if (service.database_path != self.app.config["DATABASE_PATH"]
                or service.journal.directory != self.journal.directory
                or service.backup_dir != self.app.config["BACKUP_DIR"]):
            raise RuntimeError("Restore workspace does not belong to this host")
        conn = g.get("db")
        if conn is None or conn.in_transaction:
            raise WorkbenchCommandRejected("maintenance_active", "请求连接缺失或仍有事务，恢复未执行。", 503)
        if not self():
            raise WorkbenchCommandRejected("maintenance_active", "恢复宿主或排产运行状态不可用，恢复未执行。", 503)
        with self._lock:
            row, replayed, path = self._prepare(service, request_key, intent, guard)
            if not replayed:
                self._set_state("draining", request_key)
        if replayed:
            # Never re-run old file work, even after all DB-local receipts disappeared.
            return self.journal.public(row, True)
        try:
            lease = self.gate.maintenance_owner()
            g.pop("services", None)
            g.pop("op_logger", None)
            close_workbench_request_connection(conn)
            g.pop("db")
            self.runtime.shutdown(wait=False)
            # Request threads cannot wait on the HTTP barrier themselves. This
            # coordinator never borrows Flask context or holds a maintenance lock.
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="restore-drain") as pool:
                pool.submit(self._drain, lease).result()
            return self._restore(lease, service, row, path, audit, restore_runner)
        except Exception:
            self._set_state("recovery_required", request_key)
            self.app.logger.exception("Restore host stopped; original request requires verification: %s", request_key)
            self._stop_unconfirmed(request_key)
            # A failed terminal write leaves the prior pending record intact.
            self.journal.record(row, "recovery_required", code="host_restore_unconfirmed",
                                database_origin="unconfirmed", restart_required=True,
                                message="恢复宿主未能确认安全终态，系统保持停止；请核查原请求及保护副本，不能重复恢复。")
            return self.journal.public(row)

    def audit_restore_result(self, result):
        self.verify()
        if result["action"] != "restore":
            raise ValueError("Restore host cannot audit a different file operation")
        conn = get_connection(self.db_path)
        try:
            track_workbench_request_connection(conn)
            return audit_backup_operation(conn, self.app.logger, result)
        finally:
            close_workbench_request_connection(conn)

    def _prepare(self, service, request_key, intent, guard):
        try:
            return service.prepare_restore(request_key=request_key, intent=intent, guard=guard)
        except WorkbenchCommandRejected:
            raise
        except Exception:
            # An accepted intent can reach disk before the following fsync ACK
            # fails. Do not leave HTTP/worker admission open on that path.
            try:
                recorded = self.journal.lookup(request_key)
            except Exception:
                self._stop_unconfirmed(request_key)
                raise
            if recorded is not None:
                self._stop_unconfirmed(request_key)
            raise

    def _stop_unconfirmed(self, request_key):
        self._set_state("recovery_required", request_key)
        self.runtime.shutdown(wait=False)
        if has_request_context() or current_frame() is not None:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="restore-stop") as pool:
                pool.submit(self.gate.shutdown, False).result()
        else:
            self.gate.shutdown(wait=False)

    def _drain(self, lease):
        requests_done = lease.drain(wait=True, timeout=self.timeout)
        workers_done = self.runtime.shutdown(wait=True, timeout=self.timeout)
        if requests_done is not True or workers_done is not True:
            raise RuntimeError("Restore could not prove closed HTTP responses/connections and joined worker")

    def _restore(self, lease, service, row, path, audit, restore_runner):
        self._confirm_host(lease)
        lock = schedule_service._RUN_SCHEDULE_LOCK
        if not lock.acquire(blocking=False):
            raise RuntimeError("Original scheduler lock is still held after host drain")
        try:
            self._set_state("restoring", row["request_key"])
            result = service.finish_restore(row, path, restore_runner=restore_runner, audit=audit,
                                            confirm_host=lambda: self._confirm_host(lease))
            self._confirm_host(lease)
            # Read back durable evidence; a Python return value is not a disk ACK.
            stored = self.journal.lookup(row["request_key"])
            if stored != row:
                raise RuntimeError("Restore terminal record could not be confirmed")
            state = "restart_required" if result["terminal"] else "recovery_required"
            self._set_state(state, row["request_key"])
            return result
        finally:
            lock.release()
        # Intentionally no lease.resume(): shutdown permanently closes this worker.

    def _confirm_host(self, lease):
        self.verify()
        if lease.drain() is not True:
            raise RuntimeError("Restore HTTP maintenance lease is no longer drained")


def install_workbench_system_restore_host(app, *, runtime):
    """Install only on the owning real factory app, after runtime, before HTTP."""
    existing = app.extensions.get(EXTENSION)
    if existing is not None:
        if not isinstance(existing, WorkbenchSystemRestoreHost) or existing.runtime is not runtime:
            raise RuntimeError("Restore host already foreign")
        existing.verify()
        if existing.status["state"] != "ready":
            raise RuntimeError("Restore host requires process restart")
        return existing
    if app._got_first_request:
        raise RuntimeError("Install restore host before the first HTTP request")
    controller = WorkbenchSystemRestoreHost(app, runtime)
    install_restore_status_transport(app, controller)
    app.extensions[EXTENSION] = controller
    app.extensions[GUARD] = controller
    return controller


def make_workbench_system_restore_recovery_app(database_path, journal_dir):
    """Optional pre-factory WSGI host for pending/corrupt records; no DB access.

    The launcher calls this instead of normal factory/worker initialization when
    the startup journal check raises. It retains its original launcher lock.
    Never remove a record or resume ordinary operation from this application.
    """
    from .workbench_system_restore_status import RecoveryJournal, RestoreStatusTransport
    journal = RecoveryJournal(journal_dir, database_path)
    status = {"state": "recovery_required", "restart_required": True, "automatic_resume": False,
              "operations_available": False, "result_source": "external_maintenance_journal",
              "references": "unconfirmed_do_not_use", "request_key": None}
    return RestoreStatusTransport(None, journal, lambda: dict(status))
