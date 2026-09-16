"""Target labels exercise production current-schema connections, never user databases."""

from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    ensure_current_schema_contract,
    get_schema_version,
)
from core.infrastructure.workbench_outsourcing_source_schema import install as install_sources
from core.models.workbench_outsourcing import raw_facts
from tests.workbench.outsourcing_support import OutsourcingCase


@pytest.fixture(name="targets_case")
def targets_case(tmp_path):
    path = tmp_path / "outsourcing-target-labels.sqlite"
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"))
    conn = get_connection(str(path))
    try:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        ensure_current_schema_contract(conn)
        conn.execute("BEGIN")
        install_sources(conn)
        conn.commit()
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT1','Heat treatment','external')")
        conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('XS1','Supplier','XT1',2)")
        conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('XP1','Part',?)", (b"original\x00\xff",))
        conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date) "
                     "VALUES ('XB1','XP1','Part',10,'2026-09-11','2026-09-01')")
        for index in range(1, 4):
            conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                         "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)", ("XO" + str(index), index))
        conn.commit()
        with Flask(__name__).app_context():
            yield OutsourcingCase(path, conn)
    finally:
        conn.close()


def storage(conn):
    result = {"ddl": [tuple(row) for row in conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name")]}
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        table = row[0]
        columns = [column[1] for column in conn.execute('PRAGMA table_info("' + table + '")')]
        # Keep storage bytes and type without decoding malformed legacy TEXT as UTF-8.
        selected = ",".join('typeof("' + column + '"),CASE WHEN typeof("' + column + '") IN (\'text\',\'blob\') '
                            'THEN hex("' + column + '") ELSE "' + column + '" END' for column in columns)
        result[table] = [raw_facts(tuple(item)) for item in conn.execute('SELECT ' + selected + ' FROM "' + table + '" ORDER BY rowid')]
    return result


def target_rows(case):
    with case.reader.read_snapshot():
        return case.reader.targets()["items"]


def change_origin(case, operation_ref, value):
    name = "wb_outsourcing_operationorigins_no_update"
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
    case.conn.execute('DROP TRIGGER "' + name + '"')
    case.conn.execute("UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref=? WHERE operation_ref=?", (value, operation_ref))
    case.conn.execute(guard)
    case.conn.commit()
