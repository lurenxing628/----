"""Live GET fixture bridge. Only the explicit fixture mutation changes temporary data."""

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request
from werkzeug.serving import make_server

from tests.workbench.test_calibration_support import complete_reports
from web.routes.workbench.calibration import register_calibration_routes


def prepare(case):
    ids, reports = complete_reports(case, [1.2, 1.3, 1.4, 1.5, 1.6, 1.7])
    case.command("correct", reports[-1]["report_ref"], {
        "original_revision_ref": reports[-1]["revision_ref"], "effective_processing_hours": None,
        "reason": "复核原始报工，实际加工小时尚待确认"})
    case.event(ids[-1], "start", version=2)
    case.event(ids[-1], "pause", version=2, time="2026-09-09T08:30:00")
    case.event(ids[-1], "resume", version=2, time="2026-09-09T09:00:00")
    long_code = "LONG-ORDER-" + "1234567890" * 12
    case.conn.execute("UPDATE BatchOperations SET op_code=? WHERE id=?", (long_code, ids[-1]))
    case.conn.execute("UPDATE PartOperations SET op_type_name='Turning-01' WHERE seq=1")
    for index in range(2, 24):
        case.conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours)
            VALUES ('P1',?,'T1',?,?,?)""", (index, "Turning-" + str(index).zfill(2),
            "external" if index == 23 else "internal", 0 if index == 2 else None if index == 3 else index / 10))
    case.conn.commit()
    path = Path(case.conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    assert path.name == "execution-ledger.sqlite"
    return {"database": path, "template_ref": case.template.operation_ref, "long_code": long_code,
            "report_ref": reports[-1]["report_ref"], "rows": 23}


@contextmanager
def serve(case, output):
    fixture = prepare(case)
    database = fixture["database"]
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="calibration-widget-isolated-only")
    bp = Blueprint("calibration_widget_test", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)
    journal, mutations, violations = [], [], []
    digest = lambda: hashlib.sha256(database.read_bytes()).hexdigest()

    @app.before_request
    def open_database():
        if not request.path.startswith("/api/workbench/v1/calibration"):
            return
        g.before_hash = digest()
        g.statements = []
        g.db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(g.statements.append)

    @app.after_request
    def read_proof(response):
        if hasattr(g, "db"):
            writes = [sql for sql in g.statements if sql.lstrip().split()[0].upper() in
                      {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}]
            unchanged = digest() == g.before_hash
            if writes or not unchanged:
                violations.append({"path": request.path, "writes": writes, "unchanged": unchanged})
            journal.append({"path": request.path, "method": request.method, "query": dict(request.args),
                            "status": response.status_code, "database_unchanged": unchanged,
                            "writes": writes, "snapshot": response.headers.get("X-Workbench-Snapshot")})
        return response

    @app.teardown_request
    def close_database(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.get("/__calibration_fixture__/change-source")
    def mutate_fixture():
        # Separate from product routes and their read-only connections, to provoke a real 409.
        before = digest()
        conn = sqlite3.connect(str(database))
        try:
            conn.execute("UPDATE PartOperations SET op_type_name=op_type_name||'R' WHERE seq=1")
            conn.commit()
        finally:
            conn.close()
        mutations.append({"before": before, "after": digest(), "table": "PartOperations", "sequence": 1})
        return jsonify(ok=True)

    server = make_server("127.0.0.1", 0, app, threaded=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"api_origin": "http://127.0.0.1:" + str(server.server_port),
               **{key: value for key, value in fixture.items() if key != "database"}}
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        evidence = {"temporary_database": str(database), "read_only_api": True, "journal": journal,
                    "explicit_fixture_mutations": mutations, "violations": violations, "server_stopped": not thread.is_alive()}
        (output / "calibration-server-result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        assert not violations and not thread.is_alive()
