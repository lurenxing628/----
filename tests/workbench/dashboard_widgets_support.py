"""CY isolated SQLite/browser fixture. No production factory, registry or build."""

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request
from werkzeug.serving import make_server

from core.infrastructure.workbench_dashboard_schema import install
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.dashboard_support import NOW
from web.routes.workbench.actual_gantt import register_actual_gantt_routes
from web.routes.workbench.batches import register_batch_routes
from web.routes.workbench.dashboard import register_dashboard_routes
from web.routes.workbench.execution import register_execution_routes
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes


def connect(path):
    conn = sqlite3.connect(str(path), timeout=10, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def tables(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: [tuple(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')] for name in names}


def clone(conn, path):
    with sqlite3.connect(str(path)) as target:
        conn.backup(target)
    return path


def missing_dashboard_database(path):
    # Current schema.sql includes v29; the missing-schema case must stay v28.
    schema = Path(__file__).resolve().parent / "fixtures" / "schema-v28.sql"
    with connect(path) as conn:
        conn.executescript(schema.read_text(encoding="utf-8"))
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='WorkbenchDashboardItems'").fetchone()
    return path


def prepare(case):
    conn, root = case.conn, case.path.parent
    no_data = clone(conn, root / "cy-no-data.sqlite")
    with connect(no_data) as empty:
        empty.execute("BEGIN")
        install(empty)
    accepted = case.accept()
    result = WorkbenchRunWorker(conn, clock=lambda: NOW).execute(accepted["run_ref"])
    assert len(result["candidates"]) == 4
    paths = {"missing": missing_dashboard_database(root / "cy-missing.sqlite"), "no-data": no_data}
    conn.execute("BEGIN")
    install(conn)
    conn.commit()
    paths["no-official"] = clone(conn, root / "cy-no-official.sqlite")
    conn.execute("UPDATE Batches SET due_date='2026-09-08',ready_status='no',quantity=2,part_name='精密轴套' WHERE batch_id='B1'")
    conn.execute("UPDATE Machines SET name='精车设备01' WHERE machine_id='M1'")
    conn.execute("UPDATE Operators SET name='车工甲' WHERE operator_id='O1'")
    conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) VALUES (1,'cy-fixture','success',?,'2026-09-08T12:00:00')", (json.dumps({"scheduled_ops": 1}),))
    conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1','2026-09-09T08:00:00','2026-09-09T10:00:00')", (case.op_id,))
    conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('CY-MAT','圆钢','kg',900)")
    conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) VALUES ('B1','CY-MAT',10,2,'no')")
    conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail) VALUES ('M1','2026-09-09T09:00:00','2026-09-09T11:00:00','液压检修')")
    conn.executemany("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) VALUES (?,'P1','待齐套试件',1,'2026-09-20','no')", [(f"CY-{n:02d}",) for n in range(25)])
    conn.commit()
    for name in ["light-1920", "dark-1920", "light-1392", "dark-1392", "drift", "rollback", "lost", "malformed", "unknown"]:
        paths[name] = clone(conn, root / ("cy-" + name + ".sqlite"))
    with connect(paths["unknown"]) as unknown:
        unknown.execute("UPDATE Batches SET due_date=NULL,ready_status=NULL WHERE batch_id='B1'")
    return paths, {"run_ref": result["run_ref"], "candidate_count": 4}


def proof_for(name, path, before):
    with connect(path) as conn:
        after = tables(conn)
        changed = [table for table in before if before[table] != after[table]]
        allowed = {"WorkbenchDashboardStates", "WorkbenchDashboardHistory", "WorkbenchCommandReceipts"}
        if name == "drift":
            allowed.add("BatchMaterials")
        assert set(changed) <= allowed, (name, changed)
        history = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchDashboardHistory ORDER BY sequence")] if "WorkbenchDashboardHistory" in after else []
        states = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchDashboardStates")] if "WorkbenchDashboardStates" in after else []
        receipts = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE action LIKE 'dashboard.%'")]
        return {"case": name, "database": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "history": history, "states": states,
            "receipts": receipts, "changed_tables": changed, "preserved_tables": [t for t in before if t not in changed]}


@contextmanager
def serve(case, output, monkeypatch):
    import core.services.workbench.dashboard as service_module
    import web.routes.workbench.dashboard as route_module

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 10, 12)

    monkeypatch.setattr(service_module, "datetime", Clock)
    monkeypatch.setattr(route_module, "datetime", Clock)
    paths, config = prepare(case)
    before = {}
    for name, path in paths.items():
        assert path.parent == case.path.parent and path.name.startswith("cy-")
        with connect(path) as conn:
            before[name] = tables(conn)
    app = Flask("cy-dashboard-widgets")
    app.config.update(TESTING=True, SECRET_KEY="cy-isolated-dashboard")
    bp = Blueprint("workbench", __name__)
    register_dashboard_routes(bp)
    register_actual_gantt_routes(bp)
    register_batch_routes(bp)
    register_execution_routes(bp)
    register_plan_read_routes(bp)
    register_run_candidate_routes(bp)
    register_run_history_routes(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt)
    app.register_blueprint(bp)
    journal, proofs, mutations = [], [], []

    @app.before_request
    def bind():
        name = request.cookies.get("cy_case")
        assert name in paths
        g.case_name, g.path = name, paths[name]
        g.db = connect(g.path)
        g.before = tables(g.db)

    @app.after_request
    def audit(response):
        after = tables(g.db)
        changed = [name for name in g.before if g.before[name] != after[name]]
        if request.method == "GET":
            assert not changed
        journal.append({"case": g.case_name, "path": request.path, "query": request.args.to_dict(), "method": request.method,
            "status": response.status_code, "changed_tables": changed, "input": request.get_json(silent=True), "payload": response.get_json(silent=True)})
        return response

    @app.teardown_request
    def close(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.post("/__dashboard_fixture__/mutate")
    def mutate():
        assert g.case_name in ("drift", "rollback")
        if g.case_name == "drift":
            g.db.execute("UPDATE BatchMaterials SET available_qty=3 WHERE batch_id='B1'")
        else:
            g.db.execute("CREATE TRIGGER cy_reject_history BEFORE INSERT ON WorkbenchDashboardHistory BEGIN SELECT RAISE(ABORT,'cy rollback evidence'); END")
        g.db.commit()
        mutations.append(g.case_name)
        return jsonify(ok=True)

    server = make_server("127.0.0.1", 0, app, threaded=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {**config, "api_origin": "http://127.0.0.1:" + str(server.server_port)}
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        for name, path in paths.items():
            proofs.append(proof_for(name, path, before[name]))
        (output / "dashboard-server.json").write_text(json.dumps({"journal": journal, "proofs": proofs, "mutations": mutations,
            "server_stopped": not thread.is_alive()}, ensure_ascii=False, indent=2), encoding="utf-8")
        assert not thread.is_alive()
