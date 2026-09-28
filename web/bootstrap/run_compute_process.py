"""Owned, read-only candidate computation outside the frozen Windows HTTP GIL.

The parent's WorkbenchRunWorker alone owns admission, the scheduling lock, final
freshness checks and result persistence. A failed child is never recomputed here.
"""

import logging
import multiprocessing
import os
import tempfile
import threading
from pathlib import Path

from core.infrastructure.connection_guards import query_only
from core.infrastructure.logging import safe_log
from core.infrastructure.snapshot_connection import backup_to_file, open_readonly_immutable
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_compute import CandidateRunInputError

_LOGGER = logging.getLogger(__name__)


def _parent_watchdog(control):
    # The child receives only the read end. OS closure of the parent's write end
    # also detects an abrupt parent crash. This child never writes a business DB.
    try:
        control.recv_bytes()
    except (EOFError, OSError):
        pass
    os._exit(71)


def _error_message(exc):
    if isinstance(exc, WorkbenchCommandRejected):
        return ("rejected", exc.code, str(exc), exc.status)
    if isinstance(exc, CandidateRunInputError):
        return ("input", exc.reason, str(exc), exc.issues)
    return ("failed", type(exc).__name__, str(exc))


def _raise_remote(error):
    if error[0] == "rejected":
        raise WorkbenchCommandRejected(error[1], error[2], error[3])
    if error[0] == "input":
        raise CandidateRunInputError(error[1], error[2], issues=error[3])
    raise RuntimeError("Candidate child failed: " + error[1] + ": " + error[2])


def _compute_child(snapshot_path, row, sender, control):
    threading.Thread(target=_parent_watchdog, args=(control,), daemon=True).start()
    try:
        from core.services.workbench.run.worker import WorkbenchRunWorker

        # Only this owned, consistent copy enters the child. The production path,
        # host runtime locks and the parent's writable connection are not passed.
        with open_readonly_immutable(snapshot_path) as snapshot, query_only(snapshot):
            worker = WorkbenchRunWorker(snapshot,
                progress_sink=lambda done, total: sender.send(("progress", done, total)))
            result = worker._compute(row)
        sender.send(("result", result))
    except Exception as exc:
        sender.send(("error", _error_message(exc)))
    finally:
        sender.close()


def _receive(process, receiver, on_progress):
    while True:
        try:
            if not receiver.poll(0.1):
                if process.is_alive():
                    continue
                raise RuntimeError("Candidate child exited without a result")
            message = receiver.recv()
        except EOFError as exc:
            raise RuntimeError("Candidate child closed its result channel") from exc
        if message[0] == "progress":
            done, total = message[1:]
            if type(done) is not int or type(total) is not int or not 0 <= done <= total:
                raise RuntimeError("Invalid candidate child progress")
            on_progress(done, total)
            continue
        if message[0] == "error":
            _raise_remote(message[1])
        if message[0] != "result":
            raise RuntimeError("Invalid candidate child response")
        process.join(10)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("Candidate child did not exit cleanly after its result")
        return message[1]


def run_compute_in_process(source, row, *, on_progress):
    if source.in_transaction:
        raise RuntimeError("Candidate process snapshot requires no active transaction")
    # TemporaryDirectory owns this fresh directory; nothing supplied by HTTP is
    # used as a path. Cleanup occurs after the child has released all file handles.
    with tempfile.TemporaryDirectory(prefix="aps-run-compute-") as temporary:
        path = str(Path(temporary) / "snapshot.db")
        backup_to_file(source, path)
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        child_control, parent_control = context.Pipe(duplex=False)
        process = context.Process(target=_compute_child,
            args=(path, dict(row), sender, child_control), name="aps-candidate-compute", daemon=True)
        try:
            process.start()
            safe_log(_LOGGER, "info", "Candidate read-only computation started: run_ref=%s child_pid=%s", row["run_ref"], process.pid)
            sender.close()
            child_control.close()
            return _receive(process, receiver, on_progress)
        finally:
            parent_control.close()
            sender.close()
            child_control.close()
            receiver.close()
            if process.pid is not None:
                process.join(10)
                if process.is_alive():
                    # Only this invocation's disposable, read-only child can be
                    # terminated; the parent records failure, never a result.
                    process.terminate()
                    process.join()
                process.close()
