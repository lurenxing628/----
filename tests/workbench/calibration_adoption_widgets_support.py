"""CU-only live fixture: real copied templates, reports, DDL and durable receipts."""

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request
from werkzeug.serving import make_server

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install
from core.services.workbench.production_report import WorkbenchProductionReportService
from tests.workbench.calibration_adoption_support import assert_preserved, snapshot
from tests.workbench.calibration_lineage_ui_support import template_completed
from tests.workbench.test_template_lineage_support import completed, origin
from web.routes.workbench.calibration import register_calibration_routes
from web.routes.workbench.calibration_adoption import register_calibration_adoption_routes


def prepare(case):
    case.writer = WorkbenchProductionReportService(case.conn)
    case.command("create", case.task(1, case.op_id), case.values(None, effective_processing_hours=None))
    old_ids, _ = completed(case, [8], prefix="OLD", version=2)
    case.conn.execute("UPDATE PartOperations SET unit_hours=2,op_type_name='Turning-01'")
    case.conn.commit()
    ids, reports = completed(case, [0, 1, 3, 4, 5, 6], prefix="LIVE", version=3)
    case.command("correct", reports[-1]["report_ref"], {"original_revision_ref": reports[-1]["revision_ref"],
        "effective_processing_hours": None, "reason": "原报工工时待核实，不参与定额校准"})
    case.conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours)
        VALUES ('P1',?,'T1',?,'internal',?)""", [(2, "Turning-02", 0), (3, "Turning-03", None)])
    case.conn.commit()
    other_id = case.conn.execute("SELECT id FROM PartOperations WHERE seq=2").fetchone()[0]
    missing_id = case.conn.execute("SELECT id FROM PartOperations WHERE seq=3").fetchone()[0]
    template_completed(case, other_id, [20] * 5, prefix="OTHER", version=4)
    with TransactionManager(case.conn).transaction():
        install(case.conn)
    template_ref = origin(case, ids[0])["template_operation_ref"]
    return {"template_ref": template_ref, "other_ref": case.lineage_repo.template(other_id)["template_operation_ref"],
        "missing_ref": case.lineage_repo.template(missing_id)["template_operation_ref"],
        "selected_refs": [origin(case, value)["operation_ref"] for value in ids[:5]],
        "excluded_refs": [origin(case, value)["operation_ref"] for value in old_ids + ids[-1:]],
        "unbound_ref": case.lineage_repo.instance(case.op_id)["operation_ref"]}


@contextmanager
def serve(case, output):
    config = prepare(case)
    source = Path(case.conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    assert source.name == "template-lineage.sqlite" and source.parent != Path.cwd()
    databases, before = {}, {}
    for name in ["light-1920", "dark-1920", "light-1392", "dark-1392", "disabled", "missing", "drift", "cross", "lost"]:
        database = source.parent / ("cu-adoption-" + name + ".sqlite")
        with sqlite3.connect(str(database)) as conn:
            case.conn.backup(conn)
            before[name] = snapshot(conn)
        databases[name] = database
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="cu-isolated-calibration-only", WORKBENCH_CALIBRATION_ADOPTION_ENABLED=True)
    bp = Blueprint("workbench", __name__)
    register_calibration_routes(bp)
    register_calibration_adoption_routes(bp)

    @bp.route("/api/workbench/v1/commands/<request_key>")
    def command_receipt(request_key):
        # The product's uncertain-error envelope resolves this URL; the UI uses its scoped receipt route.
        return jsonify(request_key=request_key), 404

    app.register_blueprint(bp)
    journal, mutations, proofs = [], [], []

    @app.before_request
    def open_database():
        name = request.cookies.get("cu_case")
        assert name in databases
        g.case_name, g.path = name, databases[name]
        app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] = name != "disabled"
        if request.path.startswith("/api/"):
            g.before_hash = hashlib.sha256(g.path.read_bytes()).hexdigest()
            g.db = sqlite3.connect(str(g.path))
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
            g.before = snapshot(g.db)

    @app.after_request
    def proof(response):
        if hasattr(g, "db"):
            after = snapshot(g.db)
            assert_preserved(g.before, after)
            body = response.get_json(silent=True)
            changed = after != g.before
            is_confirm = request.path.endswith("/adopt") and request.method == "POST"
            assert is_confirm or not changed, request.path
            journal.append({"case": g.case_name, "path": request.path, "method": request.method,
                "status": response.status_code, "changed": changed,
                "request": request.get_json(silent=True), "payload": body})
        return response

    @app.teardown_request
    def close_database(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.post("/__calibration_adoption_fixture__/mutate")
    def mutate():
        assert g.case_name == "drift"
        with sqlite3.connect(str(g.path)) as conn:
            conn.execute("UPDATE PartOperations SET op_type_name=op_type_name||'R' WHERE seq=1")
        mutations.append({"case": g.case_name, "table": "PartOperations", "column": "op_type_name"})
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
        for name, path in databases.items():
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            try:
                after = snapshot(conn)
                assert_preserved(before[name], after)
                audits = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCalibrationAdoptions")]
                locks = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchCalibrationQuotaLocks")]
                proofs.append({"case": name, "database": str(path), "audits": audits, "locks": locks,
                    "preserved_tables": [table for table in before[name] if before[name][table] == after[table]],
                    "changed_tables": [table for table in before[name] if before[name][table] != after[table]]})
            finally:
                conn.close()
        (output / "calibration-adoption-server.json").write_text(json.dumps({"journal": journal, "mutations": mutations,
            "proofs": proofs, "server_stopped": not thread.is_alive()}, ensure_ascii=False, indent=2), encoding="utf-8")
        assert not thread.is_alive()
