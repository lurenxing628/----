"""Frozen v30 evidence and exact additive v31 mapping assertions."""

import hashlib
import json
from contextlib import closing
from pathlib import Path

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.migrations import v30
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_dashboard_external_schema import objects
from tests.workbench.calibration_dashboard_migration_support import canonical_object
from tests.workbench.dashboard_external_support import ExternalCase
from tests.workbench.dashboard_support import follow
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.legacy_migration_current_support import V31_TABLES as V31_TABLES
from tests.workbench.legacy_migration_current_support import (
    assert_v31_receipt_maps_only as assert_v31_receipt_maps_only,
)
from tests.workbench.legacy_migration_current_support import missing_v31_issues as missing_v31_issues
from tests.workbench.outsourcing_identity_migration_support import seed_v29
from tests.workbench.outsourcing_support import OutsourcingCase
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl

FIXTURE_V30 = Path(__file__).parent / "fixtures" / "schema-v30.sql"
FIXTURE_V30_SHA = "16460ac6d0f95373eca466b101cfcc46097187760e2438fb3a8c292c28761b2e"


def fixed_v30_connection(path):
    ddl = FIXTURE_V30.read_bytes()
    assert hashlib.sha256(ddl).hexdigest() == FIXTURE_V30_SHA
    conn = connect(path)
    assert not source_ddl(conn)
    conn.executescript(ddl.decode("utf-8"))
    set_schema_version(conn, 30)
    conn.commit()
    return conn


def external_case_for(path, conn):
    case = ExternalCase(path, conn)
    case.shipments = OutsourcingCase(path, conn)
    return case


def seed_external_sources(conn, count=4):
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT1','Heat treatment','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('XS1','Supplier','XT1',2)")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('XP1','Part',?)", (b"v30-original\x00\xff",))
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date,ready_status) "
                 "VALUES ('XB1','XP1','Part',10,'2026-09-11','2026-09-01','yes')")
    for index in range(1, count + 1):
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                     "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)", ("XO" + str(index), index))
    conn.commit()


@pytest.fixture(name="external_v30_case")
def external_v30_case(tmp_path):
    path = tmp_path / "frozen-v30.sqlite"
    conn = fixed_v30_connection(path)
    try:
        seed_external_sources(conn, count=3)
        case = external_case_for(path, conn)
        with case.app.app_context():
            yield case
    finally:
        conn.close()


def seed_v30(path):
    conn = seed_v29(path)
    with TransactionManager(conn).transaction():
        v30.run(conn)
        set_schema_version(conn, 30)
    assert hashlib.sha256(FIXTURE_V30.read_bytes()).hexdigest() == FIXTURE_V30_SHA
    with closing(connect(":memory:")) as expected:
        expected.executescript(FIXTURE_V30.read_text(encoding="utf-8"))
        assert list(map(canonical_object, source_ddl(conn))) == list(map(canonical_object, source_ddl(expected)))
    seed_external_sources(conn)
    unknown = conn.execute("SELECT o.id FROM BatchOperations o JOIN WorkbenchPlanSourceRefs r ON r.source_key=CAST(o.id AS TEXT) "
                           "JOIN WorkbenchOutsourcingOperationOrigins x ON x.operation_ref=r.ref "
                           "WHERE r.kind='operation' AND r.active=1 AND x.batch_ref IS NULL LIMIT 1").fetchone()
    assert unknown is not None
    conn.execute("UPDATE BatchOperations SET source='external',supplier_id='XS1' WHERE id=?", (unknown[0],))
    conn.execute("UPDATE Batches SET due_date='2026-09-09' WHERE batch_id='B3'")
    conn.execute("UPDATE BatchOperations SET op_type_id='T1' WHERE batch_id='B3'")
    conn.commit()
    case = external_case_for(path, conn)
    with case.app.app_context():
        ledger = LedgerCase(conn)
        op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B3'").fetchone()[0]
        assert ledger.command("create", ledger.task(2, op_id), ledger.values(1),
                              key="v30-preserved-report-0001")["result"] == "committed"
        case.register()
        case.register(2, confirmedState="awaiting_confirmation")
        returned = case.register(3)
        case.returned(returned)
        item = case.item("delivery")
        assert case.command(item, follow(), key="v30-preserved-generic-0001")["result"] == "committed"
        assert case.command(case.item("delivery"), follow(owner="Second planner"),
                            key="v30-preserved-generic-0002")["result"] == "committed"
    assert get_schema_version(conn) == 30
    assert not set(objects()) & {row[1] for row in source_ddl(conn)}
    return conn


def write_migration_evidence(directory):
    """New disposable fixture only; retain full raw/DDL snapshots and real backup."""
    from core.infrastructure.database import ensure_schema
    from core.infrastructure.migration_state import current_schema_contract_issues

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    path, backups = directory / "fixture-v31.db", directory / "backups"
    with closing(seed_v30(path)) as conn:
        before, old_ddl = snapshot(conn), source_ddl(conn)
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"), backup_dir=str(backups))
    with closing(connect(path)) as conn:
        after, new_ddl = snapshot(conn), source_ddl(conn)
        assert get_schema_version(conn) == 31 and not current_schema_contract_issues(conn)
        assert_v31_receipt_maps_only(conn)
        assert set(after) - set(before) == set(V31_TABLES)
        assert {key: rows for key, rows in before.items() if key != "SchemaVersion"} == {
            key: after[key] for key in before if key != "SchemaVersion"}
        assert [row for row in new_ddl if row[1] in {old[1] for old in old_ddl}] == old_ddl
    copies = list(backups.glob("*before_migrate_v30_to_v31*.db"))
    assert len(copies) == 1
    with closing(connect(copies[0])) as conn:
        backup, backup_ddl = snapshot(conn), source_ddl(conn)
        assert backup == before and backup_ddl == old_ddl
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"), backup_dir=str(backups))
    with closing(connect(path)) as conn:
        assert snapshot(conn) == after and source_ddl(conn) == new_ddl
    assert len(list(backups.glob("*.db"))) == 1

    def evidence(rows, ddl):
        return {"ddl": ddl, "tables": {name: [[{
            "python_type": type(value).__name__, "value": value.hex() if type(value) in (bytes, float) else value,
        } for value in row] for row in values] for name, values in rows.items()}}

    result = {"fixture_sha256": FIXTURE_V30_SHA, "object_count": len(objects()),
              "before": evidence(before, old_ddl), "backup": evidence(backup, backup_ddl),
              "after": evidence(after, new_ddl), "restart_identical": True,
              "database_sha256": {str(item.relative_to(directory)): hashlib.sha256(item.read_bytes()).hexdigest()
                                  for item in (path, copies[0])}}
    output = directory / "typed-raw-ddl.json"
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    import sys

    print(write_migration_evidence(sys.argv[1]))
