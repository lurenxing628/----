"""BC fixture: real full Flask API, AJ commands, guarded temporary SQLite only."""

import importlib
import json
import os
import signal
import sys
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from live_environment import REPO, environment, install_path_guard, read_identity, write_json


def seed(api):
    from tests.workbench.test_execution_ledger_support import LedgerCase

    with api.db() as conn:
        conn.execute("UPDATE BatchOperations SET op_code='OP-01' WHERE id=1")
        case = LedgerCase(conn)
        for number in range(2, 24):
            op = case.op(f"OP-{number:02d}", seq=number)
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1','2026-09-09T08:00:00','2026-09-09T10:00:00')", (op,))
        case.event(2, "start")
        case.event(2, "finish", quantity=10)
        m2 = case.ref("machine", "M2")
    original = api.create({"actual_start": "2026-09-09T08:00:00"})
    stale_snapshot = api.read()["meta"]["snapshot_ref"]
    api.revise(original, "supplement", **api.values(0, actual_end="2026-09-09T08:30:00", effective_processing_hours=0))
    api.revise(original, completed_quantity=2, effective_processing_hours=.25, remark="BC corrected quantity and hours")
    for index in range(1, 12):
        start = datetime(2026, 9, 9, 8) + timedelta(minutes=index * 30)
        values = api.values(0 if index <= 3 else 1, actual_start=start.isoformat(),
            actual_end=(start + timedelta(minutes=30)).isoformat(), effective_processing_hours=.25)
        if index == 1:
            values["actual_machine_ref"] = m2
        api.create(values)
    api.create({"actual_start": "2026-09-09T08:00:00"}, op=3)
    data = api.read(size=50)["data"]
    assert {key: data["summary"][key] for key in ("operations", "events", "production_reports", "records")} == {
        "operations": 23, "events": 2, "production_reports": 13, "records": 15}
    assert data["summary"]["effective_processing_hours"] is None
    assert data["summary"]["known_effective_processing_hours"] == 3
    assert data["summary"]["unknown_hour_events"] == 3
    return {"machine2": m2, "operation": next(row["operation_ref"] for row in data["rows"] if row["production_report_count"] == 12),
            "batch": data["rows"][0]["batch_ref"], "summary": data["summary"], "stale_snapshot": stale_snapshot}


def serve(root):
    root = Path(root).resolve()
    read_identity(root)
    assert not (root / "db/aps-live.db").exists()
    os.environ.clear()
    os.environ.update(environment(root))
    tempfile.tempdir = str(root / "tmp")
    os.chdir(str(root))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(REPO))
    isolation = install_path_guard(root)
    app = importlib.import_module("app").app
    from flask import request
    from werkzeug.serving import make_server

    from tests.workbench.report_execution_ledger_support import report_ledger_api

    api = report_ledger_api.__wrapped__(app.test_client())
    assert Path(api.path).resolve() == root / "db/aps-live.db"
    @app.after_request
    def journal(response):
        with (root / "requests.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"method": request.method, "path": request.path,
                "query": request.args.to_dict(), "status": response.status_code}) + "\n")
        return response

    expected = seed(api)
    before = api.state()
    server = make_server("127.0.0.1", 0, app)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    worker.start()
    write_json(root / "ready.json", {"origin": "http://127.0.0.1:" + str(server.server_port), "root": str(root), "expected": expected})
    try:
        stop.wait()
    finally:
        server.shutdown()
        worker.join(timeout=10)
        server.server_close()
        write_json(root / "final.json", {"database_unchanged": api.state() == before, "stopped": not worker.is_alive(),
            "sqlite_connections": sorted(set(isolation["sqlite_connections"])), "violations": isolation["violations"]})


if __name__ == "__main__":
    serve(sys.argv[1])
