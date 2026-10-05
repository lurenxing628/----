"""Eight actual batch requests queue without keeping a SQLite read transaction."""
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from flask import g

from core.services.workbench.batch import facts as facts_module
from core.services.workbench.batch.bulk import WorkbenchBatchBulkService
from core.services.workbench.batch.file_codec import write_batch_file
from core.services.workbench.batch.files import WorkbenchBatchFileService
from core.services.workbench.batch.operations import WorkbenchBatchOperationService
from core.services.workbench.batch.quantity_split import WorkbenchQuantitySplitService
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
from tests.workbench.batch_support import BASE, batch_database, detail, list_data, ref_for

_batch_fixture = batch_database


def test_queued_batch_reads_leave_database_available_and_keep_complete_results(batch_client, tmp_path, monkeypatch):
    path = str(tmp_path / "budget.sqlite")
    conn = sqlite3.connect(path)
    batch_client.batch_conn.backup(conn)
    conn.close()
    app = batch_client.application
    arrival = threading.Barrier(9)
    one_projecting, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    entered = []
    active, peak = 0, 0

    def connection():
        g.db = sqlite3.connect(path, timeout=0.1)
        g.db.row_factory = sqlite3.Row
        arrival.wait(timeout=10)

    app.before_request_funcs[None] = [connection]
    @app.teardown_request
    def close_connection(error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()
    original = facts_module.project_workflow_snapshot

    def project(raw):
        nonlocal active, peak
        assert not g.db.in_transaction
        with lock:
            entered.append(threading.get_ident())
            active += 1
            peak = max(peak, active)
            if len(entered) == 1:
                one_projecting.set()
        try:
            assert release.wait(timeout=10)
            return original(raw)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(facts_module, "project_workflow_snapshot", project)

    def request():
        with app.test_client() as client:
            response = client.get(BASE)
            assert response.status_code == 200, response.get_json()
            return response.get_json()["data"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        tasks = [pool.submit(request) for _ in range(8)]
        try:
            arrival.wait(timeout=10)
            assert one_projecting.wait(timeout=10)
            with lock:
                assert len(entered) == 1
            # Even the queued seven HTTP requests must not hold SQLite SHARED locks.
            with sqlite3.connect(path, timeout=0.1) as writer:
                writer.execute("UPDATE Batches SET remark='after-budget-read' WHERE batch_id='FREE-001'")
                writer.commit()
        finally:
            release.set()
        results = [future.result(timeout=20) for future in tasks]
    assert peak == 1
    assert len(entered) == len(results) == 8
    remarks = []
    for result in results:
        rows = [row for row in result["entities"] if row["business_code"] == "FREE-001"]
        assert len(rows) == 1 and len(rows[0]["operations"]) == 1
        remarks.append(rows[0]["fields"]["remark"])
    assert remarks.count("keep-hidden") == 1
    assert remarks.count("after-budget-read") == 7


def test_fifo_budget_serves_waiters_before_a_returning_reader():
    from web.routes.workbench.read_budget import ReadBudget

    budget = ReadBudget(1)
    order = []
    threads = []
    # Hold admission while enqueueing deterministic arrivals, then immediately
    # try again from the releasing reader. A semaphore can let that reader barge.
    with budget.slot():
        for number in range(6):
            def read(index=number):
                with budget.slot():
                    order.append(index)
            with budget._condition:
                previous = len(budget._waiting)
                thread = threading.Thread(target=read)
                thread.start()
                assert budget._condition.wait_for(lambda: len(budget._waiting) > previous, timeout=5)
            threads.append(thread)
    with budget.slot():
        order.append(6)
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert order == list(range(7))


def test_read_budget_releases_after_projection_error():
    import pytest

    from web.routes.workbench.read_budget import ReadBudget

    budget = ReadBudget(1)
    with pytest.raises(ValueError):
        with budget.slot():
            raise ValueError("invalid facts")
    with budget.slot():
        assert budget._available == 0
    assert budget._available == 1


def _preview_request(client, route):
    if route == "split":
        from tests.workbench.test_batch_quantity_split import prepare

        prepare(client)
        snapshot = detail(client)["meta"]["snapshot_ref"]
        return lambda: client.post(BASE + "/" + ref_for(client) + "/split-preview", json={"snapshot_ref": snapshot, "input": {"as_of_date": "2026-09-28"}})
    if route == "sync":
        # The current instance is internal; its replacement template is external.
        client.batch_conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='OT1'")
        client.batch_conn.commit()
        snapshot = detail(client)["meta"]["snapshot_ref"]
        return lambda: client.post(BASE + "/" + ref_for(client) + "/sync-preview", json={"snapshot_ref": snapshot, "input": {}})
    snapshot = list_data(client)["meta"]["snapshot_ref"]
    if route == "bulk":
        return lambda: client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": snapshot,
                                   "input": {"action": "update", "refs": [ref_for(client)], "patch": {"remark": "budget"}}})
    if route == "export":
        return lambda: client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": {"snapshot_ref": snapshot}})
    content = write_batch_file([["FREE-001", "P1", 5, None, None, None, None, "budget"]], template=True)
    return lambda: client.post(BASE + "/import-preview", data={"file": (BytesIO(content), "batch.xlsx"), "mode": "overwrite",
                               "scope": "{}", "snapshot_ref": snapshot}, content_type="multipart/form-data")


@pytest.mark.parametrize("route,service,method,detached", [
    ("split", WorkbenchQuantitySplitService, "plan", True), ("bulk", WorkbenchBatchBulkService, "plan", True),
    ("export", WorkbenchBatchQueryService, "selection", True), ("import", WorkbenchBatchFileService, "preview", True),
    # The sync preview re-reads the stored process workflow, so it keeps its read transaction.
    ("sync", WorkbenchBatchOperationService, "sync_preview", False)])
def test_batch_previews_queue_on_the_shared_slot_and_load_the_ledger_once(batch_client, monkeypatch, route, service, method, detached):
    from web.routes.workbench import read_budget

    send = _preview_request(batch_client, route)
    conn = batch_client.batch_conn
    loads, slots, computed = [], [], []
    original_tables, original_slot, original_method = WorkbenchBatchFactsRepository.whole_tables, read_budget.BATCH_READ_SLOTS.slot, getattr(service, method)

    def whole_tables(repo):
        loads.append(True)
        return original_tables(repo)

    def slot():
        slots.append(True)
        return original_slot()

    def compute(instance, *args, **kwargs):
        computed.append((conn.in_transaction, read_budget.BATCH_READ_SLOTS._available))
        return original_method(instance, *args, **kwargs)

    monkeypatch.setattr(WorkbenchBatchFactsRepository, "whole_tables", whole_tables)
    monkeypatch.setattr(read_budget.BATCH_READ_SLOTS, "slot", slot)
    monkeypatch.setattr(service, method, compute)
    response = send()
    assert response.status_code == 200, response.get_json()
    assert slots == [True] and loads == [True]
    assert computed == [(not detached, 0)]
    assert not conn.in_transaction


def test_import_preview_parses_the_workbook_before_queueing_for_the_read_slot(batch_client, monkeypatch):
    from core.services.workbench.batch import files as files_module
    from web.routes.workbench import read_budget

    send = _preview_request(batch_client, "import")
    original, parsed = files_module.read_batch_file, []

    def read_batch_file(content):
        parsed.append((read_budget.BATCH_READ_SLOTS._available, batch_client.batch_conn.in_transaction))
        return original(content)

    monkeypatch.setattr(files_module, "read_batch_file", read_batch_file)
    response = send()
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["count"] == 1
    assert parsed == [(1, False)]
