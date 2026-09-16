"""DN isolated real DI routes, original SQLite rows and current/frozen DDL."""

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request
from werkzeug.serving import make_server

from core.infrastructure.workbench_outsourcing_schema import contract_issues, install
from core.infrastructure.workbench_outsourcing_source_schema import install as install_sources
from core.models.workbench_outsourcing import raw_facts
from core.services.workbench.outsourcing import WorkbenchOutsourcingService
from core.services.workbench.outsourcing_commands import WorkbenchOutsourcingCommandService
from web.routes.workbench.dashboard import register_dashboard_routes
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.outsourcing import register_outsourcing_routes

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 9, 10, 12)


def connect(path):
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def tables(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: raw_facts([tuple(r) for r in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]) for name in names}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def seed(conn):
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('DN-T','外协热处理','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('DN-S','恒信热处理厂','DN-T',2)")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('DN-P','精密传动轴',?)", (b"original\x00\xff",))
    for batch in ("DN-B1", "DN-B2"):
        conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date) VALUES (?,'DN-P','精密传动轴',10,'2026-09-15','2026-09-01')", (batch,))
    for index in range(1, 26):
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                     "VALUES (?,?,?,'DN-T','外协热处理','external','DN-S',2)", (f"DN-O{index:02d}", "DN-B2" if index == 25 else "DN-B1", index))
    conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) VALUES (1,'dn-preserved','success','{}','2026-09-07T12:00:00')")
    conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) VALUES (1,1,'2026-09-07T08:00:00','2026-09-09T12:00:00')")
    conn.execute("INSERT INTO OperationExecutionEvents(schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,created_by,idempotency_key,request_fingerprint,previous_state_revision,remark) "
                 "VALUES (1,1,1,'DN-B1','schedule','adopted','start','processing','2026-09-07T08:00:00','original-operator','dn-original-key','dn-original-fp','1:0:0',?)", (b"execution\x00\xfe",))
    conn.commit()


def prepare(root, legacy_source=False):
    base = root / "dn-base.sqlite"
    current = os.environ.get("OUTSOURCING_UI_SCHEMA") == "current"
    if current:
        from core.infrastructure.database import ensure_schema
        ensure_schema(str(base), schema_path=str(HERE.parents[1] / "schema.sql"), backup_dir=None)
    with connect(base) as conn:
        if not current:
            conn.executescript((HERE / "fixtures" / "schema-v29.sql").read_text(encoding="utf-8"))
            conn.execute("UPDATE SchemaVersion SET version=29 WHERE id=1")
            conn.commit()
        seed(conn)
        if legacy_source:
            from tests.workbench.outsourcing_legacy_source_support import erase_fixture_birth_evidence
            erase_fixture_birth_evidence(conn)
        source = tables(conn)
        conn.execute("BEGIN")
        install(conn)
        install_sources(conn)
        conn.commit()
        after = tables(conn)
        assert all(after[k] == v for k, v in source.items())
        assert contract_issues(conn) == []
        version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0]
        if current:
            from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
            issues = current_schema_contract_issues(conn)
            assert version == CURRENT_SCHEMA_VERSION and issues == [], (version, issues)
        names = [theme + "-" + str(width) for width in (1920, 1392) for theme in ("light", "dark")]
        names += ["lost", "malformed", "drift", "rollback", "stale", "missing"]
        paths = {}
        for name in names:
            path = root / ("dn-" + name + ".sqlite")
            with connect(path) as target:
                conn.backup(target)
            paths[name] = path
    with connect(paths["missing"]) as conn:
        conn.execute("DROP TRIGGER wb_outsourcing_fact_sequence")
    return paths, {"schema_mode": "current" if current else "v29-plus-real-DI-DDL", "schema_version": version, "legacy_source": legacy_source,
                   "baseline_database": str(base), "baseline_sha256": hashlib.sha256(base.read_bytes()).hexdigest()}


def proof(name, path, before):
    with connect(path) as conn:
        after = tables(conn)
        changed = [t for t in before if before[t] != after[t]]
        allowed = {"WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts", "WorkbenchCommandReceipts",
                   "WorkbenchOutsourcingSourceConfirmations"}
        if name == "drift":
            allowed |= {"Suppliers", "WorkbenchEntityRefs"}
        assert set(changed) <= allowed, (name, changed)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        return {"case": name, "database": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "changed_tables": changed, "preserved_tables": [t for t in before if t not in changed],
                "table_proofs": {t: {"before_sha256": digest(before[t]), "after_sha256": digest(after[t])} for t in before},
                "facts": [dict(r) for r in conn.execute("SELECT * FROM WorkbenchOutsourcingFacts ORDER BY outsourcing_ref,sequence")],
                "headers": [dict(r) for r in conn.execute("SELECT * FROM WorkbenchOutsourcingReceipts")],
                "source_confirmations": [dict(r) for r in conn.execute("SELECT * FROM WorkbenchOutsourcingSourceConfirmations")],
                "receipts": [dict(r) for r in conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE action='outsourcing.confirm'")],
                "plan_rows": len(after["Schedule"]), "execution_rows": len(after["OperationExecutionEvents"])}


@contextmanager
def serve(root, output, monkeypatch, legacy_source=False):
    import web.routes.workbench.outsourcing as module

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 10, 12)

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "WorkbenchOutsourcingService", lambda conn: WorkbenchOutsourcingService(conn, clock=lambda: NOW))
    monkeypatch.setattr(module, "WorkbenchOutsourcingCommandService", lambda conn, **kwargs: WorkbenchOutsourcingCommandService(
        conn, clock=lambda: NOW, actor_provider=lambda: "dn-system-operator", **kwargs))
    import core.services.workbench.dashboard as dashboard_service
    import web.routes.workbench.dashboard as dashboard_route
    monkeypatch.setattr(dashboard_service, "datetime", Clock)
    monkeypatch.setattr(dashboard_route, "datetime", Clock)
    paths, config = prepare(root, legacy_source=legacy_source)
    before = {}
    for name, path in paths.items():
        with connect(path) as conn:
            before[name] = tables(conn)
    app = Flask("dn-outsourcing-widgets")
    app.config.update(SECRET_KEY="dn-isolated-test", TESTING=True)
    bp = Blueprint("workbench", __name__)
    register_outsourcing_routes(bp)
    register_dashboard_routes(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt)
    app.register_blueprint(bp)
    journal = []

    @app.before_request
    def bind():
        name = request.cookies.get("dn_case")
        assert name in paths
        g.case_name, g.db = name, connect(paths[name])
        g.before = tables(g.db)

    @app.after_request
    def audit(response):
        after = tables(g.db)
        changed = [name for name in g.before if g.before[name] != after[name]]
        if request.method == "GET" or request.path.endswith("/preview"):
            assert not changed
        journal.append({"case": g.case_name, "path": request.path, "query": request.args.to_dict(), "method": request.method,
                        "status": response.status_code, "changed_tables": changed})
        return response

    @app.teardown_request
    def close(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.post("/__outsourcing_fixture__/mutate")
    def mutate():
        assert g.case_name in ("drift", "rollback")
        if g.case_name == "drift":
            g.db.execute("UPDATE Suppliers SET name='核实后的厂名' WHERE supplier_id='DN-S'")
        else:
            g.db.execute("CREATE TRIGGER dn_rollback BEFORE INSERT ON WorkbenchOutsourcingFacts BEGIN SELECT RAISE(ABORT,'dn rollback evidence'); END")
        g.db.commit()
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
        proofs = [proof(name, path, before[name]) for name, path in paths.items()]
        (output / "outsourcing-server.json").write_text(json.dumps({"journal": journal, "proofs": proofs,
            "server_stopped": not thread.is_alive(), **config}, ensure_ascii=False, indent=2), encoding="utf-8")
        assert not thread.is_alive()
