"""Local v27 fixtures, typed preservation evidence and SQLite VM measurements.

Original CJ failure, independently reproduced once before implementation:
test_plan_persistent_identity.py:464: assert 291031000 < 100000000
Python 3.8.10 / SQLite 3.35.5; unchanged current schema.sql and original test.
The historical regression is deliberately retained, never retried for a pass.
"""

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.migrations import v27
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects

ORIGINAL_VM_BUDGET = 100000000
ORIGINAL_FAILURE_STEPS = 291031000


def load_v27(conn, *, seed_before_v27=None):
    """Reconstruct v27 from main's immutable v26 fixture and frozen v27 migration."""
    assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
    path = Path(__file__).parent / "fixtures" / "schema-v26.sql"
    conn.executescript(path.read_text(encoding="utf-8"))
    if seed_before_v27 is not None:
        seed_before_v27(conn)
        conn.commit()
    v27.run(conn)
    set_schema_version(conn, 27)
    conn.commit()
    return conn


@pytest.fixture(name="v27_conn")
def v27_fixture(mem_conn):
    return load_v27(mem_conn)


def typed_rows(conn):
    result = {}
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for table in names:
        quoted = '"' + table.replace('"', '""') + '"'
        columns = [row[1] for row in conn.execute("PRAGMA table_info(" + quoted + ")")]
        types = ",".join('typeof("' + column.replace('"', '""') + '")' for column in columns)
        result[table] = sorted((tuple(row) for row in conn.execute("SELECT *," + types + " FROM " + quoted)), key=repr)
    return result


def schema_rows(conn):
    return [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name,type")]


@contextmanager
def measured_sql(conn):
    result = {"ticks": 0, "statements": []}

    def progress():
        result["ticks"] += 1
        return int(result["ticks"] * 1000 >= ORIGINAL_VM_BUDGET)

    conn.set_progress_handler(progress, 1000)
    conn.set_trace_callback(result["statements"].append)
    try:
        yield result
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_trace_callback(None)
        result["steps_upper"] = (result["ticks"] + 1) * 1000
        result["selects"] = sum(sql.lstrip().upper().startswith("SELECT") for sql in result["statements"])


def born_select():
    """Extract the actual frozen trigger SELECT, not a rewritten lookalike."""
    sql = template_lineage_objects()["wb_lineage_operation_born"]
    return sql[sql.index(" SELECT ") + 1:sql.rindex(";")].replace("NEW.ref", "?").replace("NEW.source_key", "?")


def born_program(conn):
    program = conn.execute("EXPLAIN INSERT INTO WorkbenchPlanSourceRefs(ref,kind,source_key) "
                           "VALUES (?, 'operation', ?)", ("a" * 48, "1"))
    active, result = False, []
    for row in program:
        if row[0] == 0:
            active = row[5] == "-- TRIGGER wb_lineage_operation_born"
        if active:
            result.append(tuple(row))
    return result


def freeze_sql_generated_values(conn):
    """Only paired semantic replay fixes entropy/time; performance uses real SQLite."""
    counter = [0]

    def blob(size):
        counter[0] += 1
        return hashlib.shake_256(str(counter[0]).encode("ascii")).digest(size)

    conn.create_function("randomblob", 1, blob)
    conn.create_function("current_timestamp", 0, lambda: "2026-09-09 08:00:00")
    conn.create_function("strftime", 2, lambda fmt, value: "2026-09-09T08:00:00.000Z")


def replay_writes(conn):
    freeze_sql_generated_values(conn)
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('REPLAY-P','Replay')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('REPLAY-B','REPLAY-P',2)")
    for index, op_id in enumerate((-7, 1, 9223372036854775807)):
        conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name,setup_hours,unit_hours) "
                     "VALUES (?,?,'REPLAY-B',?,?,NULL,1.25)",
                     (op_id, "OP-" + str(index), index + 1, sqlite3.Binary(b"type\x00\xff")))
    conn.execute("UPDATE BatchOperations SET unit_hours=3 WHERE id=1")
    conn.execute("UPDATE BatchOperations SET unit_hours=1.25 WHERE id=1")
    conn.execute("UPDATE Batches SET quantity=3 WHERE batch_id='REPLAY-B'")
    conn.execute("INSERT OR IGNORE INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) "
                 "VALUES (1,'ignored','REPLAY-B',99,'ignored')")
    conn.execute("INSERT OR REPLACE INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) "
                 "VALUES (1,'replacement','REPLAY-B',2,'replacement')")
    conn.execute("DELETE FROM BatchOperations WHERE id=-7")
    conn.commit()
