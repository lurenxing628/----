"""DG live HTTP support: actual CO/CW samples, browser adoption, isolated SQLite."""

import base64
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from flask import Blueprint, Flask, g, request
from werkzeug.serving import make_server

from core.services.workbench.process_file_codec import encode_process_file
from tests.workbench.calibration_adoption_support import snapshot
from tests.workbench.process_quota_protection_file_receipt_support import assert_tables_preserved, file_rows
from web.routes.workbench.calibration import register_calibration_routes
from web.routes.workbench.calibration_adoption import register_calibration_adoption_routes
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.process_files import register_process_file_routes
from web.routes.workbench.process_reads import register_process_read_routes


def files():
    rows = {
        "mixed": file_rows({"sequence": 1, "unit_hours": 99, "setup_hours": 9}, {"sequence": 2, "unit_hours": 8}),
        "allskip": file_rows({"sequence": 1, "unit_hours": 99, "setup_hours": 9}),
        "noop": file_rows({"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 7}),
        "setup": file_rows({"sequence": 1, "unit_hours": 3, "setup_hours": 9}),
        "setup_blank": file_rows({"sequence": 1, "setup_hours": 10}),
    }
    return {name + "." + fmt: base64.b64encode(encode_process_file("hours", values, fmt).content).decode("ascii")
            for name, values in rows.items() for fmt in ("csv", "xlsx")}


@contextmanager
def serve(case, output):
    source = Path(case.db_path).resolve()
    assert source.name == "template-lineage.sqlite" and Path.cwd() not in source.parents
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCalibrationQuotaLocks").fetchone()[0] == 0
    names = [layout + "-" + theme + "-" + str(width) for layout in ("mixed", "allskip")
             for width in (1920, 1392) for theme in ("light", "dark")] + ["setup", "noop", "drift"]
    databases, before = {}, {}
    for name in names:
        database = output / ("dg-quota-" + name + ".sqlite")
        with sqlite3.connect(str(database)) as conn:
            case.conn.backup(conn)
            before[name] = snapshot(conn)
        databases[name] = database
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="dg-isolated-quota-ui", WORKBENCH_CALIBRATION_ADOPTION_ENABLED=True)
    bp = Blueprint("workbench", __name__)
    for register in (register_calibration_routes, register_calibration_adoption_routes,
                     register_process_read_routes, register_process_file_routes):
        register(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt, methods=["GET"])
    app.register_blueprint(bp)
    journal, proofs = [], []

    @app.before_request
    def open_database():
        name = request.cookies.get("dg_case")
        assert name in databases
        g.case_name = name
        g.db = sqlite3.connect(str(databases[name]))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.before = snapshot(g.db)

    @app.after_request
    def prove(response):
        body = response.get_json(silent=True)
        after = snapshot(g.db)
        allowed = ()
        if response.status_code == 200 and request.method == "POST" and request.path.endswith("/adopt"):
            allowed = ("PartOperations", "WorkbenchEntityRefs", "WorkbenchCalibrationAdoptions",
                       "WorkbenchCalibrationQuotaLocks", "WorkbenchCommandReceipts")
        elif response.status_code == 200 and request.method == "POST" and request.path.endswith("/confirm"):
            allowed = ("WorkbenchCommandReceipts",)
            if body["result"] == "committed":
                allowed += ("PartOperations", "WorkbenchEntityRefs")
        assert_tables_preserved(g.before, after, allowed)
        journal.append({"case": g.case_name, "method": request.method, "path": request.path,
                        "status": response.status_code, "input": request.get_json(silent=True), "payload": body,
                        "request_key": getattr(g, "workbench_request_key", None),
                        "changed_tables": [table for table in after if after[table] != g.before[table]]})
        return response

    @app.teardown_request
    def close_database(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    server = make_server("127.0.0.1", 0, app, threaded=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"api_origin": "http://127.0.0.1:" + str(server.server_port), "files": files(),
               "template_ref": case.template_ref, "part_ref": case.ref("part", "P1")}
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        for name, database in databases.items():
            conn = sqlite3.connect(str(database))
            conn.row_factory = sqlite3.Row
            try:
                after = snapshot(conn)
                assert_tables_preserved(before[name], after, ("PartOperations", "WorkbenchEntityRefs",
                    "WorkbenchCalibrationAdoptions", "WorkbenchCalibrationQuotaLocks", "WorkbenchCommandReceipts"))
                proofs.append({"case": name, "database": str(database),
                    "audits": [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCalibrationAdoptions")],
                    "locks": [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCalibrationQuotaLocks")],
                    "templates": [dict(row) for row in conn.execute("SELECT seq,setup_hours,unit_hours FROM PartOperations ORDER BY seq")],
                    "receipts": [dict(row) for row in conn.execute("SELECT request_key,outcome_json FROM WorkbenchCommandReceipts")],
                    "preserved_tables": [table for table in after if before[name][table] == after[table]]})
            finally:
                conn.close()
        (output / "process-quota-server.json").write_text(json.dumps({"journal": journal, "proofs": proofs,
            "server_stopped": not thread.is_alive()}, ensure_ascii=False, indent=2), encoding="utf-8")
        assert not thread.is_alive()
