"""Current-schema temporary SQLite evidence for the legacy batch copy entry."""

import re
from collections import Counter

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_template_lineage_schema import contract_issues
from core.services.scheduler.batch_service import BatchService
from core.services.workbench.template_lineage import TemplateLineageWriter
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.test_execution_ledger_support import LedgerCase, all_rows


class LegacyBatchLineageCase(LedgerCase):
    template_id: int

    def __init__(self, conn):
        super().__init__(conn)
        self.batch_service = BatchService(conn)
        self.lineage_writer = TemplateLineageWriter(conn)
        self.lineage_repo = WorkbenchTemplateLineageRepository(conn)


@pytest.fixture(name="legacy_case")
def legacy_case(schema_conn):
    assert contract_issues(schema_conn) == []
    with TransactionManager(schema_conn).transaction():
        insert_row(schema_conn, "OpTypes", dict(op_type_id="T1", name="Turning"))
        insert_row(schema_conn, "OpTypes", dict(op_type_id="legacy-type", name="Legacy raw type"))
        insert_row(schema_conn, "Machines", dict(machine_id="M1", name="Lathe", op_type_id="T1"))
        insert_row(schema_conn, "Operators", dict(operator_id="O1", name="Operator"))
        insert_row(schema_conn, "OperatorMachine", dict(operator_id="O1", machine_id="M1"))
        insert_row(schema_conn, "Suppliers", dict(supplier_id="S1", name="Supplier"))
        insert_row(schema_conn, "Parts", dict(part_no="P1", part_name="Part"))
        insert_row(schema_conn, "Materials", dict(material_id="MAT1", name="Steel", stock_qty=1000))
        for seq in range(1, 4):
            insert_row(schema_conn, "PartOperations", dict(part_no="P1", seq=seq, op_type_id="T1",
                op_type_name="Turning", source="internal", setup_hours=0, unit_hours=1))
    case = LegacyBatchLineageCase(schema_conn)
    case.template_id = schema_conn.execute("SELECT id FROM PartOperations WHERE seq=1").fetchone()[0]
    return case


def operations(case, batch_id):
    return [dict(row) for row in case.conn.execute(
        "SELECT * FROM BatchOperations WHERE batch_id=? ORDER BY seq,piece_id", (batch_id,))]


def seed_scale(case, count=50):
    # Keep an inactive historical ref in the full-table preservation oracle too.
    case.batch_service.create_batch_from_template("RETIRED", "P1", 10)
    case.batch_service.delete("RETIRED")
    sources = ["SRC-" + str(index).zfill(3) for index in range(count)]
    for code in sources:
        case.batch_service.create_batch_from_template(code, "P1", 10, due_date="2026-10-01",
            priority="urgent", ready_status="no", ready_date="2026-09-15", remark="keep-source")
        insert_row(case.conn, "BatchMaterials", dict(batch_id=code, material_id="MAT1",
            required_qty=10, available_qty=7, ready_status="no"))
        case.conn.commit()
    ids = [row["id"] for code in sources for row in operations(case, code)]
    assert len(ids) == count * 3
    case.plan(1, ids)
    for code in sources:
        rows = operations(case, code)
        case.command("create", case.task(1, rows[0]["id"]), case.values(10))
        case.event(rows[1]["id"], "start", batch_id=code)
        case.event(rows[1]["id"], "finish", quantity=10, batch_id=code)
    with TransactionManager(case.conn).transaction():
        case.conn.execute("UPDATE Batches SET status='completed',part_name='historical-name'")
        case.conn.execute("UPDATE BatchOperations SET status='scheduled',machine_id='M1',operator_id='O1'")
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    assert len(all_rows(case.conn)["WorkbenchProductionReports"]) == count
    assert len(all_rows(case.conn)["OperationExecutionEvents"]) == count * 2
    return sources


def fail_last_origin(case, destination_code):
    # The trigger executes after the real instance insert, inside its SAVEPOINT.
    assert destination_code in ("DST-049", "SINGLE")
    case.conn.execute("""CREATE TRIGGER fail_legacy_copy_origin BEFORE INSERT ON WorkbenchTemplateLineageOrigins
        WHEN NEW.operation_ref=(SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1
            AND alternate_key='""" + destination_code + """_03')
        BEGIN SELECT RAISE(ABORT,'legacy last operation failure'); END""")
    case.conn.commit()


def assert_raw_copy(source, copied, destination_code):
    expected = dict(source)
    for key in ("id", "created_at"):
        expected.pop(key)
    suffix = "_" + source["piece_id"] if source["piece_id"] is not None else ""
    expected.update(batch_id=destination_code, op_code=destination_code + "_" + str(source["seq"]).zfill(2) + suffix,
                    status="pending")
    actual = {key: copied[key] for key in expected}
    assert actual == expected
    assert {key: type(value) for key, value in actual.items()} == {key: type(value) for key, value in expected.items()}
    assert copied["id"] != source["id"]


def assert_only_copy_appends(before, after, batch_count, operation_count):
    assert before.keys() == after.keys()
    appended = {"Batches": batch_count, "BatchOperations": operation_count,
                "WorkbenchEntityRefs": batch_count, "WorkbenchPlanSourceRefs": operation_count,
                "WorkbenchTemplateLineageOrigins": operation_count, "WorkbenchTemplateLineageEvents": operation_count,
                "WorkbenchDashboardItems": batch_count * 2, "WorkbenchOutsourcingOperationOrigins": operation_count}
    for table, rows in before.items():
        if table in appended:
            assert after[table][:len(rows)] == rows, table
            assert len(after[table]) == len(rows) + appended[table], table
        elif table == "WorkbenchPlanIdentityClock":
            assert after[table] == [(1, rows[0][1] + operation_count)]
        elif table == "sqlite_sequence" and operation_count:
            expected = dict(rows)
            expected["BatchOperations"] += operation_count
            expected["WorkbenchTemplateLineageEvents"] += operation_count
            assert dict(after[table]) == expected
        else:
            assert after[table] == rows, table
    assert_dashboard_copy_items(before, after, batch_count)
    assert_operation_birth_items(before, after)


def assert_dashboard_copy_items(before, after, batch_count):
    new_batches = after["Batches"][len(before["Batches"]):]
    new_refs = after["WorkbenchEntityRefs"][len(before["WorkbenchEntityRefs"]):]
    assert len(new_batches) == len(new_refs) == batch_count
    assert {row[2] for row in new_refs} == {row[0] for row in new_batches}
    assert all(row[1] == "batch" and row[4:6] == (1, 1) for row in new_refs)
    old_items = before["WorkbenchDashboardItems"]
    items = after["WorkbenchDashboardItems"]
    assert items[:len(old_items)] == old_items
    additions = items[len(old_items):]
    assert len(additions) == batch_count * 2
    expected = Counter((category, row[0], None) for row in new_refs for category in ("delivery", "material"))
    assert Counter(row[1:] for row in additions) == expected
    assert len({row[0] for row in items}) == len(items)
    assert all(re.fullmatch(r"[0-9a-f]{48}", row[0]) for row in additions)


def assert_operation_birth_items(before, after):
    operations = after["BatchOperations"][len(before["BatchOperations"]):]
    refs = after["WorkbenchPlanSourceRefs"][len(before["WorkbenchPlanSourceRefs"]):]
    batches = after["WorkbenchEntityRefs"][len(before["WorkbenchEntityRefs"]):]
    batch_refs = {row[2]: row[0] for row in batches}
    owners = {str(row[0]): batch_refs[row[2]] for row in operations}
    assert len(refs) == len(operations) == len(owners)
    assert all(row[1] == "operation" and row[-1] == 1 for row in refs)
    assert {row[2] for row in refs} == set(owners)
    additions = after["WorkbenchOutsourcingOperationOrigins"][len(before["WorkbenchOutsourcingOperationOrigins"]):]
    assert Counter(additions) == Counter((row[0], owners[row[2]]) for row in refs)
