"""Frozen v25 schema with already-recorded production facts, not a fake version tag."""

import sqlite3
from pathlib import Path

from core.infrastructure.migration_state import set_schema_version
from tests.workbench.test_execution_ledger_support import LedgerCase

FIXTURE_V25 = Path(__file__).parent / "fixtures" / "schema-v25.sql"


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(conn):
    result = {}
    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [row[1] for row in conn.execute("PRAGMA table_info(" + quoted + ")")]
        types = ",".join('typeof("' + column.replace('"', '""') + '")' for column in columns)
        result[name] = sorted((tuple(row) for row in conn.execute("SELECT *," + types + " FROM " + quoted)), key=repr)
    return result


def source_ddl(conn):
    return [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]


def seed_v25(path):
    conn = connect(path)
    conn.executescript(FIXTURE_V25.read_text(encoding="utf-8"))
    set_schema_version(conn, 25)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('P1','Part','unchanged private note')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10)")
    case = LedgerCase(conn)
    case.op_id = case.op()
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    event_id = case.event(case.op_id, "finish")
    legacy = conn.execute("SELECT legacy_fact_ref FROM WorkbenchExecutionLegacyFacts WHERE id=?", (event_id,)).fetchone()[0]
    case.command("create", case.task(1, case.op_id), {
        **case.values(10), "legacy_fact_ref": legacy, "reason": "Preserve supplemented legacy facts",
        "remark": "retained report", "declared_operator": "fixture operator",
    }, key="v25-preserved-report-0001")
    conn.execute("UPDATE Parts SET remark=? WHERE part_no='P1'", (sqlite3.Binary(b"retained\x00metadata\xff"),))
    conn.commit()
    return conn
