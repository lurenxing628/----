"""Real spawn, SQLite snapshots, parent-only commits, and child failure safety."""

import multiprocessing
import os
import threading
import time

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.run.jobs_facts import capture_run_facts
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_jobs_support import service
from tests.workbench.run_runtime_support import install
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from web.bootstrap import run_compute_process as process_module


def _crash_child(*args):
    os._exit(73)


def test_real_spawn_persists_once_and_preserves_source_business_facts(job_case, monkeypatch):
    case = job_case
    for sequence in range(2, 11):
        case.operation(seq=sequence, unit_hours=0.001)
    case.conn.commit()
    accepted = case.accept()
    original_facts = capture_run_facts(case.conn)
    receive = process_module._receive
    children, progress = [], []
    def observe(process, receiver, on_progress):
        children.append(process)
        assert process.pid != os.getpid() and process.is_alive()
        return receive(process, receiver, on_progress)
    monkeypatch.setattr(process_module, "_receive", observe)
    worker = WorkbenchRunWorker(case.conn, compute_runner=process_module.run_compute_in_process,
        progress_sink=lambda done, total: progress.append((os.getpid(), done, total)))
    result = worker.execute(accepted["run_ref"])
    assert result["state"] == "complete" and len(result["candidates"]) == 4
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 40
    assert capture_run_facts(case.conn) == original_facts
    assert len(children) == 1 and children[0]._closed
    assert progress and all(pid == os.getpid() for pid, _, _ in progress)
    assert progress[-1][1:] == (4, 4)
    assert worker.execute(accepted["run_ref"]) == result
    assert len(children) == 1


def test_parent_rechecks_freshness_after_child_computes_its_original_snapshot(job_case):
    case = job_case
    accepted = case.accept()
    changed = []
    def change_source(done, total):
        if not changed:
            case.conn.execute("UPDATE Batches SET quantity=4 WHERE batch_id='B1'")
            case.conn.commit()
            changed.append(True)
    worker = WorkbenchRunWorker(case.conn, compute_runner=process_module.run_compute_in_process,
        progress_sink=change_source)
    with pytest.raises(WorkbenchCommandRejected) as error:
        worker.execute(accepted["run_ref"])
    assert error.value.code == "snapshot_stale" and changed
    state = service(case.conn).get(accepted["run_ref"])
    assert state["state"] == "failed" and state["error"]["code"] == "snapshot_stale"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0
    assert case.conn.execute("SELECT quantity FROM Batches WHERE batch_id='B1'").fetchone()[0] == 4


def test_child_stale_snapshot_error_retains_its_domain_code(job_case):
    accepted = job_case.accept()
    def stale(source, row, *, on_progress):
        return process_module.run_compute_in_process(source, dict(row, facts_hash="0" * 64), on_progress=on_progress)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunWorker(job_case.conn, compute_runner=stale).execute(accepted["run_ref"])
    assert error.value.code == "snapshot_stale"
    assert service(job_case.conn).get(accepted["run_ref"])["error"]["code"] == "snapshot_stale"


def test_child_crash_is_terminal_failure_without_a_retry_or_partial_results(job_case, monkeypatch):
    accepted = job_case.accept()
    monkeypatch.setattr(process_module, "_compute_child", _crash_child)
    calls = []
    def compute(source, row, *, on_progress):
        calls.append(row["run_ref"])
        return process_module.run_compute_in_process(source, row, on_progress=on_progress)
    with pytest.raises(RuntimeError, match="Candidate child"):
        WorkbenchRunWorker(job_case.conn, compute_runner=compute).execute(accepted["run_ref"])
    state = service(job_case.conn).get(accepted["run_ref"])
    assert state["state"] == "failed" and not state["result_persisted"]
    assert calls == [accepted["run_ref"]]
    assert case_count(job_case, "WorkbenchRunCandidates") == 0
    assert case_count(job_case, "WorkbenchRunCandidateTasks") == 0


def case_count(case, table):
    assert table in ("WorkbenchRunCandidates", "WorkbenchRunCandidateTasks")
    return case.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def test_parent_callback_failure_closes_the_child_and_leaves_no_live_process(job_case):
    accepted = job_case.accept()
    before = {child.pid for child in multiprocessing.active_children()}
    def fail(done, total):
        raise RuntimeError("progress sink failed")
    with pytest.raises(RuntimeError, match="progress sink failed"):
        WorkbenchRunWorker(job_case.conn, compute_runner=process_module.run_compute_in_process,
            progress_sink=fail).execute(accepted["run_ref"])
    assert {child.pid for child in multiprocessing.active_children()} == before
    assert not service(job_case.conn).get(accepted["run_ref"])["result_persisted"]


def test_existing_transaction_does_not_create_a_child(job_case):
    job_case.conn.execute("BEGIN")
    try:
        with pytest.raises(RuntimeError, match="no active transaction"):
            process_module.run_compute_in_process(job_case.conn, {}, on_progress=lambda *_: None)
        assert job_case.conn.in_transaction
    finally:
        job_case.conn.rollback()


def test_uncertain_parent_result_write_never_restarts_child(job_case, monkeypatch):
    accepted = job_case.accept()
    calls = []
    def compute(source, row, *, on_progress):
        calls.append(row["run_ref"])
        return process_module.run_compute_in_process(source, row, on_progress=on_progress)
    worker = WorkbenchRunWorker(job_case.conn, compute_runner=compute)
    original = worker.results.save
    def fail_save(ref, candidates):
        original(ref, candidates)
        raise OSError("result write acknowledgement lost")
    monkeypatch.setattr(worker.results, "save", fail_save)
    with pytest.raises(WorkbenchCommandUncertain):
        worker.execute(accepted["run_ref"])
    assert calls == [accepted["run_ref"]]
    assert case_count(job_case, "WorkbenchRunCandidates") == 0
    assert service(job_case.conn).get(accepted["run_ref"])["state"] == "running"


def test_runtime_shutdown_keeps_ownership_until_real_child_is_reaped(owned_case, monkeypatch):
    runtime = install(owned_case)
    runtime._compute_runner = process_module.run_compute_in_process
    entered, release = threading.Event(), threading.Event()
    receive = process_module._receive
    children = []
    def pause(process, receiver, on_progress):
        children.append(process)
        entered.set()
        assert release.wait(15)
        return receive(process, receiver, on_progress)
    monkeypatch.setattr(process_module, "_receive", pause)
    accepted = owned_case.accept()
    runtime(accepted["run_ref"])
    try:
        assert entered.wait(15)
        assert runtime.shutdown(timeout=0.01) is False
        assert children[0].pid is not None
    finally:
        release.set()
    assert runtime.shutdown(timeout=20)
    assert children[0]._closed
    assert service(owned_case.conn).get(accepted["run_ref"])["state"] == "complete"


@pytest.mark.parametrize("entry", ["app.py", "app_new_ui.py"])
def test_spawn_entry_import_does_not_create_an_application(entry, monkeypatch):
    import runpy
    from pathlib import Path

    from web.bootstrap import entrypoint

    def reject(*args, **kwargs):
        raise AssertionError("spawn must not create an application or open a production DB")
    monkeypatch.setattr(entrypoint, "create_app_with_mode", reject)
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] / entry), run_name="__mp_main__")
    assert "app" not in namespace


def _watchdog_child(control):
    threading.Thread(target=process_module._parent_watchdog, args=(control,), daemon=True).start()
    while True:
        time.sleep(10)


def _abrupt_parent(channel):
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    child = context.Process(target=_watchdog_child, args=(reader,), daemon=True)
    child.start()
    reader.close()
    channel.send(child.pid)
    channel.recv()
    # Deliberately bypass multiprocessing's normal daemon cleanup.
    os._exit(72)


@pytest.mark.skipif(os.name != "nt", reason="Win7 process-handle watchdog proof")
def test_abrupt_parent_exit_stops_only_its_disposable_child():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    context = multiprocessing.get_context("spawn")
    root, remote = context.Pipe()
    parent = context.Process(target=_abrupt_parent, args=(remote,))
    parent.start()
    remote.close()
    handle = None
    try:
        assert root.poll(15)
        child_pid = root.recv()
        handle = kernel.OpenProcess(0x100000 | 0x0001, False, child_pid)
        assert handle
        root.send("exit")
        parent.join(10)
        assert parent.exitcode == 72
        assert kernel.WaitForSingleObject(handle, 10000) == 0
    finally:
        if handle:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                kernel.TerminateProcess(handle, 74)
            kernel.CloseHandle(handle)
        if parent.is_alive():
            parent.terminate()
            parent.join(10)
        parent.close()
        root.close()
