"""DI fixtures load frozen v29 DDL, then explicitly install the DI extension."""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g, jsonify

from core.infrastructure.database import get_connection
from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.workbench_outsourcing_schema import install
from core.models.workbench_outsourcing import raw_facts
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.outsourcing import WorkbenchOutsourcingService
from core.services.workbench.outsourcing_commands import WorkbenchOutsourcingCommandService
from web.routes.workbench.outsourcing import register_outsourcing_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

NOW = datetime(2026, 9, 10, 12)
ROOT = "/api/workbench/v1/outsourcing"
FROZEN_V29 = Path(__file__).parent / "fixtures" / "schema-v29.sql"
FROZEN_V29_SHA256 = "d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648"


def original_rows(conn):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
             if not row[0].startswith(("WorkbenchOutsourcing", "sqlite_")) and row[0] != "WorkbenchCommandReceipts"]
    result = {}
    for table in names:
        columns = [row[1] for row in conn.execute('PRAGMA table_info("' + table + '")')]
        selected = ",".join('CASE WHEN 1 THEN "' + column + '" END' for column in columns)
        result[table] = [raw_facts(tuple(row)) for row in conn.execute('SELECT ' + selected + ' FROM "' + table + '" ORDER BY rowid')]
    return result


class OutsourcingCase:
    def __init__(self, path, conn):
        self.path, self.conn, self.counter = path, conn, 0
        self.reader = WorkbenchOutsourcingService(conn, clock=lambda: NOW)

    def entity_ref(self, kind, code):
        return self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, code)).fetchone()[0]

    def operation_ref(self, code):
        return self.conn.execute("SELECT r.ref FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o ON r.source_key=CAST(o.id AS TEXT) "
                                 "WHERE r.kind='operation' AND r.active=1 AND o.op_code=?", (code,)).fetchone()[0]

    def payload(self, *, merged=False, **patch):
        refs = [self.operation_ref("XO1"), self.operation_ref("XO2")] if merged else [self.operation_ref("XO1")]
        return {"target": {"kind": "merged" if merged else "single", "batch_ref": self.entity_ref("batch", "XB1"),
                           "supplier_ref": self.entity_ref("supplier", "XS1"), "operation_refs": refs},
                "sent": "2026-09-07T09:00:00", "planned": "2026-09-09T12:00:00", "returned": None,
                "confirmedState": "in_transit", "declared_operator": "Shipping clerk", "reason": "Checked dispatch sheet 01", **patch}

    def writer(self, conn=None):
        return WorkbenchOutsourcingCommandService(conn or self.conn, clock=lambda: NOW, actor_provider=lambda: "local-operator",
                                                  context_factory=issue_write_context)

    def preview(self, payload, conn=None):
        return self.writer(conn).preview(payload)

    def confirm(self, preview, *, key=None, conn=None, payload=None):
        self.counter += 1
        token = preview["write_context"]["write_token"]
        return self.writer(conn).execute(payload or preview["input"], request_key=key or f"outsourcing-key-{self.counter:08d}",
            validate_context=lambda subject, action, facts: validate_write_context(token, subject, action, facts))

    def detail(self, ref):
        with self.reader.read_snapshot():
            return self.reader.detail(ref)["item"]


@pytest.fixture(name="outsourcing_case")
def outsourcing_case(tmp_path):
    path = tmp_path / "outsourcing.sqlite"
    ddl = FROZEN_V29.read_bytes()
    assert hashlib.sha256(ddl).hexdigest() == FROZEN_V29_SHA256
    conn = get_connection(str(path))
    assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
    conn.executescript(ddl.decode("utf-8"))
    set_schema_version(conn, 29)
    conn.commit()
    assert get_schema_version(conn) == 29
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'WorkbenchOutsourcing%'").fetchone()
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name IN "
                            "('wb_plan_source_ref_insert_guard','wb_plan_task_ref_insert_guard')").fetchone()
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT1','Heat treatment','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('XS1','Supplier','XT1',2)")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('XP1','Part',?)", (b"original\x00\xff",))
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date) VALUES ('XB1','XP1','Part',10,'2026-09-11','2026-09-01')")
    for index in range(1, 4):
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                     "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)", ("XO" + str(index), index))
    conn.commit()
    before = original_rows(conn)
    conn.execute("BEGIN")
    install(conn)
    conn.commit()
    assert original_rows(conn) == before
    assert get_schema_version(conn) == 29
    with Flask(__name__).app_context():
        yield OutsourcingCase(path, conn)
    conn.close()


def api(case, monkeypatch):
    import web.routes.workbench.outsourcing as module

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(module, "WorkbenchOutsourcingService", lambda conn: WorkbenchOutsourcingService(conn, clock=lambda: NOW))
    monkeypatch.setattr(module, "WorkbenchOutsourcingCommandService", lambda conn, **kwargs: WorkbenchOutsourcingCommandService(
        conn, clock=lambda: NOW, actor_provider=lambda: "http-local-operator", **kwargs))
    app = Flask(__name__)
    bp = Blueprint("workbench", __name__)
    register_outsourcing_routes(bp)

    @bp.route("/api/workbench/v1/commands/<request_key>")
    def command_receipt(request_key):
        return jsonify({"ok": True, "data": WorkbenchCommandService(g.db).lookup(request_key)})

    app.register_blueprint(bp)

    @app.before_request
    def bind():
        g.db = get_connection(str(case.path))

    @app.teardown_request
    def close(error):
        g.db.close()

    return app.test_client()
