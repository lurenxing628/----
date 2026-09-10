"""One explicitly owned host dispatcher; install before requests or maintenance.

The caller retains the launcher locks until shutdown(wait=True) returns True.
This module never creates/migrates a database and never uses Flask's g.db.
"""

import os
import queue
import sys
import threading
import time
from contextlib import closing

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import TERMINAL_STATES, validate_run_ref
from core.services.scheduler import schedule_service
from core.services.workbench.run_jobs import WorkbenchRunService
from core.services.workbench.run_worker import WorkbenchRunWorker

from .launcher_paths import _normalize_db_path_for_runtime
from .workbench_request_lifecycle import lookup_workbench_request_lifecycle
from .workbench_run_runtime_lock import RunRuntimeLockProof, RunRuntimeOwnershipError

_INSTALL_LOCK = threading.RLock()  # App/DB registration only, never scheduling.
_RUNTIMES = {}
_EXTENSION = "workbench_run_runtime"
_DISPATCHER = "workbench_run_dispatcher"
_ENABLED = "WORKBENCH_RUN_JOBS_ENABLED"


class WorkbenchRunRuntime:
    def __init__(self, app):
        self.app = app
        self.db_path = _normalize_db_path_for_runtime(app.config.get("DATABASE_PATH"))
        self.proof = None
        self.recovery = None
        self._condition = threading.Condition()
        self._queue = queue.Queue()
        self._pending = set()
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self._ready = False
        self._reason = "runtime_lock_not_supplied"
        self._publish(False, self._reason)

    @property
    def ready(self):
        with self._condition:
            return self._ready

    @property
    def status(self):
        with self._condition:
            return {"ready": self._ready, "reason": self._reason,
                    "closed": self._closed, "pending": sorted(self._pending),
                    "recovery": self.recovery}

    def _publish(self, enabled, reason):
        self._ready, self._reason = enabled, reason
        self.app.config[_ENABLED] = enabled
        gate = lookup_workbench_request_lifecycle(self.db_path) if enabled else None
        writes_enabled = bool(enabled and gate is not None and gate.status["state"] == "accepting")
        self.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = writes_enabled
        self.app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] = writes_enabled
        self.app.config["WORKBENCH_POINT_RENDERING_ENABLED"] = writes_enabled
        self.app.config["WORKBENCH_RUN_RUNTIME_REASON"] = reason
        if enabled:
            self.app.extensions[_DISPATCHER] = self
        elif self.app.extensions.get(_DISPATCHER) is self:
            self.app.extensions.pop(_DISPATCHER)

    def _disable(self, reason):
        with self._condition:
            self._publish(False, reason)
        self.app.logger.error("Workbench run runtime disabled: db=%s reason=%s", self.db_path, reason)

    def _verify(self):
        if _normalize_db_path_for_runtime(self.app.config.get("DATABASE_PATH")) != self.db_path:
            raise RunRuntimeOwnershipError("runtime_database_config_changed")
        if self.proof is None:
            raise RunRuntimeOwnershipError("runtime_lock_not_supplied")
        self.proof.verify()

    def _executor_is_active(self, _executor_ref):
        # Only valid for this DB's sole managed entry point, before dispatch starts
        # or after our worker has returned. Recovery itself owns the scheduler lock.
        try:
            self._verify()
        except (RunRuntimeOwnershipError, OSError):
            return None
        return False

    def _recover(self):
        self._verify()
        with closing(get_connection(self.db_path)) as conn:
            result = WorkbenchRunService(conn).recover_unfinished_runs(
                executor_is_active=self._executor_is_active)
        self.recovery = result
        self._verify()
        if result["scheduling_busy"]:
            raise RunRuntimeOwnershipError("recovery_scheduling_busy")
        if result["pending"]:
            raise RunRuntimeOwnershipError("awaiting_reconciliation: " + ",".join(result["pending"]))

    def _start(self, runtime_lock):
        if (self.app.debug and not getattr(sys, "frozen", False)
                and os.environ.get("WERKZEUG_RUN_MAIN", "").strip().lower() != "true"):
            self._disable("debug_reloader_parent")
            return
        try:
            self.proof = RunRuntimeLockProof(self.db_path, runtime_lock)
            self._recover()
            self._thread = threading.Thread(target=self._serve, name="workbench-run-worker", daemon=True)
            self._thread.start()
            with self._condition:
                self._publish(True, "ready")
            self.app.logger.info("Workbench run recovery complete; dispatcher enabled: db=%s recovery=%s",
                                 self.db_path, self.recovery)
        except Exception as exc:
            if self._thread is not None and self._thread.ident is None:
                self._thread = None
            self._disable(str(exc))
            self.app.logger.exception("Workbench run runtime installation failed: db=%s", self.db_path)

    def __call__(self, run_ref):
        validate_run_ref(run_ref)
        with self._condition:
            if not self._ready or self._closed or self._stop.is_set():
                raise RuntimeError("Workbench run dispatcher unavailable: " + self._reason)
            try:
                self._verify()
            except Exception:
                self._publish(False, "runtime_ownership_lost")
                self._stop.set()
                self.app.logger.exception("Workbench run dispatch ownership lost: run_ref=%s db=%s",
                                          run_ref, self.db_path)
                raise
            if self._thread is None or not self._thread.is_alive():
                self._publish(False, "runtime_worker_stopped")
                raise RuntimeError("Workbench run worker stopped")
            if run_ref not in self._pending:
                self._pending.add(run_ref)
                self._queue.put(run_ref)

    def _execute(self, run_ref):
        while not self._stop.is_set():
            self._verify()
            with closing(get_connection(self.db_path)) as conn:
                row = WorkbenchRunService(conn).get(run_ref)
                if row["state"] != "queued" or row["stage"] != "queued":
                    if row["state"] not in TERMINAL_STATES:
                        self._disable("awaiting_reconciliation: " + run_ref)
                        self._stop.set()
                    return
                try:
                    WorkbenchRunWorker(conn).execute(run_ref)
                    return
                except WorkbenchCommandRejected as exc:
                    if exc.code != "scheduling_busy":
                        raise
            # Never hold a DB transaction while waiting. The worker must acquire
            # the original non-reentrant lock itself, so release this wait probe.
            lock = schedule_service._RUN_SCHEDULE_LOCK
            if lock.acquire(timeout=0.1):
                lock.release()

    def _run_one(self, run_ref):
        try:
            self._execute(run_ref)
        except Exception:
            self.app.logger.exception("Workbench run worker failed; reconcile original run_ref=%s db=%s",
                                      run_ref, self.db_path)
            try:
                # New connection, never retry compute after an uncertain COMMIT.
                # Do not reconcile other legitimately queued runs after a failure
                # that the worker has already durably recorded.
                self._verify()
                with closing(get_connection(self.db_path)) as conn:
                    state = WorkbenchRunService(conn).get(run_ref)
                if state["state"] in TERMINAL_STATES:
                    return
                self._disable("awaiting_reconciliation: " + run_ref)
                self._stop.set()
                self._recover()
            except Exception as exc:
                self._disable(str(exc))
                self.app.logger.exception("Workbench run reconciliation failed: run_ref=%s db=%s",
                                          run_ref, self.db_path)
                self._stop.set()

    def _serve(self):
        try:
            while not self._stop.is_set():
                try:
                    run_ref = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    self._run_one(run_ref)
                finally:
                    with self._condition:
                        self._pending.discard(run_ref)
                        self._condition.notify_all()
                    self._queue.task_done()
        finally:
            with self._condition:
                if self._pending:
                    self.app.logger.warning("Workbench shutdown retains undispatched original runs: db=%s run_refs=%s",
                                            self.db_path, sorted(self._pending))
                self._pending.clear()
                self._publish(False, self._reason if not self._ready else "runtime_worker_stopped")
                self._condition.notify_all()

    def wait_idle(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._pending:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def shutdown(self, wait=True, timeout=None):
        """Stop admission, finish an executing worker; True permits lock release.

        Queued, unclaimed work stays durable for next startup reconciliation.
        Call from the server/lifecycle thread, never from the worker itself.
        """
        with self._condition:
            self._closed = True
            self._publish(False, "runtime_shutdown")
            self._stop.set()
        thread = self._thread
        if wait and thread is not None:
            if thread is threading.current_thread():
                raise RuntimeError("Workbench worker cannot join itself")
            thread.join(timeout)
        finished = thread is None or not thread.is_alive()
        if finished:
            with _INSTALL_LOCK:
                if _RUNTIMES.get(self.db_path) is self:
                    _RUNTIMES.pop(self.db_path)
        return finished


def stop_workbench_runs_for_database(db_path):
    """Exit-backup guard; no database connection or lifecycle initialization."""
    key = _normalize_db_path_for_runtime(db_path)
    with _INSTALL_LOCK:
        if not key and _RUNTIMES:
            raise RuntimeError("Cannot associate exit backup with a managed database")
        runtime = _RUNTIMES.get(key)
    return runtime is None or runtime.shutdown(wait=True)


def install_workbench_run_runtime(app, *, runtime_lock=None):
    """Install after schema setup, before any API/automatic maintenance is opened.

    Pass acquire_runtime_lock(..., db_path=DATABASE_PATH)'s original payload.
    No proof means disabled without opening the database. Same live app install
    is idempotent; a second app must not borrow a dispatcher, even during shutdown.
    A closed app cannot be restarted; create a new app explicitly after joining.
    """
    with _INSTALL_LOCK:
        runtime = app.extensions.get(_EXTENSION)
        if runtime is not None:
            if not isinstance(runtime, WorkbenchRunRuntime) or runtime._closed:
                raise RuntimeError("Workbench runtime already closed or foreign")
            if runtime.db_path != _normalize_db_path_for_runtime(app.config.get("DATABASE_PATH")):
                raise RuntimeError("Workbench runtime database changed")
            if runtime.proof is not None:
                if not runtime.proof.matches(runtime.db_path, runtime_lock):
                    raise RuntimeError("Workbench runtime reinstall ownership differs")
                try:
                    runtime._verify()
                except Exception:
                    runtime._disable("runtime_ownership_lost")
                    raise
                return runtime
            if runtime_lock is None:
                return runtime
        else:
            if _DISPATCHER in app.extensions:
                app.config[_ENABLED] = False
                raise RuntimeError("Workbench dispatcher already installed outside managed runtime")
            runtime = WorkbenchRunRuntime(app)
            app.extensions[_EXTENSION] = runtime
        if runtime_lock is None:
            return runtime
        existing = _RUNTIMES.get(runtime.db_path)
        if existing is not None and existing is not runtime:
            runtime._disable("runtime_database_already_registered")
            raise RuntimeError("Workbench database already has a managed runtime")
        _RUNTIMES[runtime.db_path] = runtime
        runtime._start(runtime_lock)
        if runtime._thread is None:
            _RUNTIMES.pop(runtime.db_path)
        return runtime
