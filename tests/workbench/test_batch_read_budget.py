"""Eight actual batch requests queue without keeping a SQLite read transaction."""
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import g

from core.services.workbench.batch import facts as facts_module
from tests.workbench.batch_support import BASE, batch_database

_batch_fixture = batch_database


def test_queued_batch_reads_leave_database_available_and_keep_complete_results(batch_client, tmp_path, monkeypatch):
    path = str(tmp_path / "budget.sqlite")
    conn = sqlite3.connect(path)
    batch_client.batch_conn.backup(conn)
    conn.close()
    app = batch_client.application
    arrival = threading.Barrier(9)
    two_projecting, release = threading.Event(), threading.Event()
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
            if len(entered) == 2:
                two_projecting.set()
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
            assert two_projecting.wait(timeout=10)
            with lock:
                assert len(entered) == 2
            # Even the queued six HTTP requests must not hold SQLite SHARED locks.
            with sqlite3.connect(path, timeout=0.1) as writer:
                writer.execute("UPDATE Batches SET remark='after-budget-read' WHERE batch_id='FREE-001'")
                writer.commit()
        finally:
            release.set()
        results = [future.result(timeout=20) for future in tasks]
    assert peak == 2
    assert len(entered) == len(results) == 8
    remarks = []
    for result in results:
        rows = [row for row in result["entities"] if row["business_code"] == "FREE-001"]
        assert len(rows) == 1 and len(rows[0]["operations"]) == 1
        remarks.append(rows[0]["fields"]["remark"])
    assert remarks.count("keep-hidden") == 2
    assert remarks.count("after-budget-read") == 6
