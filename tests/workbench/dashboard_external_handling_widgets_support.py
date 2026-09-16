"""DX isolated v30 migration plus explicit DT helper; never relabel as current."""

import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request
from werkzeug.serving import make_server

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.migrations.v30 import run as migrate_v30
from core.infrastructure.workbench_dashboard_external_schema import contract_issues, install
from core.infrastructure.workbench_outsourcing_schema import contract_issues as outsourcing_issues
from core.infrastructure.workbench_outsourcing_source_schema import install as install_sources
from core.infrastructure.workbench_plan_identity_write_guard import contract_issues as identity_issues
from core.services.workbench.outsourcing import WorkbenchOutsourcingService
from core.services.workbench.outsourcing_commands import WorkbenchOutsourcingCommandService
from tests.workbench.outsourcing_support import FROZEN_V29, FROZEN_V29_SHA256
from tests.workbench.outsourcing_widgets_support import NOW, connect, digest, seed, tables
from web.routes.workbench.dashboard import register_dashboard_routes
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.outsourcing import register_outsourcing_routes

HERE = Path(__file__).resolve().parent


def database(path, helper=False):
    ddl = FROZEN_V29.read_bytes()
    assert hashlib.sha256(ddl).hexdigest() == FROZEN_V29_SHA256
    with connect(path) as conn:
        conn.executescript(ddl.decode("utf-8"))
        set_schema_version(conn, 29)
        conn.commit()
        migrate_v30(conn)
        assert not outsourcing_issues(conn) and not identity_issues(conn)
        set_schema_version(conn, 30)
        conn.commit()
        seed(conn)
        before = tables(conn)
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'WorkbenchDashboardExternal%'").fetchone()
        if helper:
            conn.execute("BEGIN")
            install(conn)
            conn.commit()
            assert not contract_issues(conn)
            assert all(tables(conn)[name] == rows for name, rows in before.items())
        assert get_schema_version(conn) == 30
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def schema(conn):
    return [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name")]


def prepare(root):
    baseline = database(root / "dx-v30-base.sqlite")
    names = [theme + "-" + str(width) for width in (1920, 1392) for theme in ("light", "dark")]
    names += ["current30", "missing", "unknown", "lost", "malformed", "stale"]
    paths = {}
    with connect(baseline) as source:
        for name in names:
            path = root / ("dx-" + name + ".sqlite")
            with connect(path) as conn:
                source.backup(conn)
                # v32 起外协读取守卫（WorkbenchOutsourcingRepository.require_schema）要求来源确认表齐全；冻结 v30 夹具没有这张表，
                # 浏览器要读外协登记的每个库都补装。current30 只是不装仪表盘外协处置助手，仍锁住 handling_supported=False。
                conn.execute("BEGIN")
                install_sources(conn)
                conn.commit()
                if name != "current30":
                    conn.execute("BEGIN")
                    install(conn)
                    conn.commit()
                    assert not contract_issues(conn)
                if name == "missing":
                    conn.execute("DROP TRIGGER wb_dashboard_external_history_no_update")
            paths[name] = path
    return paths, {"schema_mode": "frozen-v29 + real-v30-migration + explicit-DT-helper + v32-source-confirmations (except current30)",
                   "schema_version": 30, "baseline_database": str(baseline),
                   "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest()}


def proof(name, path, before, original_schema):
    with connect(path) as conn:
        after = tables(conn)
        changed = [table for table in before if before[table] != after[table]]
        allowed = {"WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts",
                   "WorkbenchDashboardExternalItems", "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory", "WorkbenchCommandReceipts"}
        if name == "stale":
            allowed |= {"Suppliers", "WorkbenchEntityRefs"}
        assert set(changed) <= allowed, (name, changed)
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert get_schema_version(conn) == 30
        assert schema(conn) == original_schema
        result = {"case": name, "database": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "schema_version": 30, "changed_tables": changed, "preserved_tables": [t for t in before if t not in changed],
                  "ddl_before_sha256": digest(original_schema), "ddl_after_sha256": digest(schema(conn)),
                  "table_proofs": {t: {"before_sha256": digest(before[t]), "after_sha256": digest(after[t])} for t in before}}
        for key, table in (("history", "WorkbenchDashboardExternalHistory"), ("states", "WorkbenchDashboardExternalStates"),
                           ("facts", "WorkbenchOutsourcingFacts"), ("receipts", "WorkbenchCommandReceipts")):
            result[key] = [dict(r) for r in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] if table in after else []
        return result


@contextmanager
def serve(root, output, monkeypatch):
    import core.services.workbench.dashboard as dashboard_service
    import web.routes.workbench.dashboard as dashboard_route
    import web.routes.workbench.outsourcing as outsourcing_route

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 10, 12)

    monkeypatch.setattr(dashboard_service, "datetime", Clock)
    monkeypatch.setattr(dashboard_route, "datetime", Clock)
    monkeypatch.setattr(outsourcing_route, "datetime", Clock)
    monkeypatch.setattr(outsourcing_route, "WorkbenchOutsourcingService", lambda conn: WorkbenchOutsourcingService(conn, clock=lambda: NOW))
    monkeypatch.setattr(outsourcing_route, "WorkbenchOutsourcingCommandService", lambda conn, **kwargs: WorkbenchOutsourcingCommandService(
        conn, clock=lambda: NOW, actor_provider=lambda: "dx-local-operator", **kwargs))
    paths, config = prepare(root)
    before, schemas = {}, {}
    for name, path in paths.items():
        with connect(path) as conn:
            before[name] = tables(conn)
            schemas[name] = schema(conn)
        write_json(output / (name + "-sql-before.json"), before[name])
        write_json(output / (name + "-ddl.json"), schemas[name])
    app = Flask("dx-external-handling-widgets")
    app.config.update(TESTING=True, SECRET_KEY="dx-isolated-test")
    bp = Blueprint("workbench", __name__)
    register_dashboard_routes(bp)
    register_outsourcing_routes(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt)
    app.register_blueprint(bp)
    journal = []

    @app.before_request
    def bind():
        name = request.cookies.get("dx_case")
        assert name in paths
        g.case_name, g.db = name, connect(paths[name])
        g.before = tables(g.db)
        g.ddl = schema(g.db)

    @app.after_request
    def audit(response):
        after = tables(g.db)
        assert schema(g.db) == g.ddl
        assert set(after) == set(g.before)
        changed = [table for table in g.before if g.before[table] != after[table]]
        if request.method == "GET" or request.path.endswith("/preview"):
            assert not changed
        if request.method == "POST" and "/dashboard/items/" in request.path:
            assert set(changed) <= {"WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory", "WorkbenchCommandReceipts"}
        journal.append({"case": g.case_name, "path": request.path, "query": request.args.to_dict(), "method": request.method,
                        "status": response.status_code, "changed_tables": changed,
                        "ddl_before_sha256": digest(g.ddl), "ddl_after_sha256": digest(schema(g.db)),
                        "table_proofs": {t: {"before_sha256": digest(g.before[t]), "after_sha256": digest(after[t])} for t in g.before},
                        "input": request.get_json(silent=True), "payload": response.get_json(silent=True)})
        return response

    @app.teardown_request
    def close(_error):
        if hasattr(g, "db"):
            g.db.close()

    @app.post("/__dx_fixture__/mutate")
    def mutate():
        assert g.case_name in ("unknown", "stale")
        if g.case_name == "unknown":
            g.db.execute("DROP TRIGGER wb_outsourcing_facts_no_update")
            g.db.execute("PRAGMA ignore_check_constraints=ON")
            g.db.execute("UPDATE WorkbenchOutsourcingFacts SET confirmed_state='invalid-original'")
            from core.infrastructure.workbench_outsourcing_schema import objects
            g.db.execute(objects()["wb_outsourcing_facts_no_update"])
        else:
            g.db.execute("UPDATE Suppliers SET name='来源已核实变更' WHERE supplier_id='DN-S'")
        g.db.commit()
        return jsonify(ok=True)

    server = make_server("127.0.0.1", 0, app, threaded=False)
    assert server.server_port not in (52392, 58448, 64612)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {**config, "api_origin": "http://127.0.0.1:" + str(server.server_port)}
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        proofs = []
        for name, path in paths.items():
            proofs.append(proof(name, path, before[name], schemas[name]))
            with connect(path) as conn:
                write_json(output / (name + "-sql-after.json"), tables(conn))
        write_json(output / "dashboard-external-server.json", {**config, "journal": journal, "proofs": proofs,
                                                               "server_stopped": not thread.is_alive()})
        assert not thread.is_alive()
