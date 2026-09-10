"""Real domain fixtures and independent whole-database preservation oracles."""

from __future__ import annotations

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import seed_resources
from tests.workbench.process_route_support import all_table_snapshot
from tests.workbench.process_workflow_support import confirm_all, seed_workflow

CREATE = {"business_code": "NEW-001", "label": "new part", "route_raw": " 10turning\r\n20coating  ", "remark": " note "}
PARTS = ("DROP-A", "DROP-B")


@pytest.fixture(name="part_actions_conn")
def part_actions_database(schema_conn):
    seed_resources(schema_conn, relations=True)
    schema_conn.execute("UPDATE OpTypes SET name='legacy-turning' WHERE op_type_id='OT1'")
    seed_workflow(schema_conn, PARTS[0])
    seed_workflow(schema_conn, PARTS[1], catalog=False)
    schema_conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,remark)
        VALUES ('DROP-A-unused','DROP-A',8,9,'merged',7.25,'unused legacy rule')""")
    for table in ("Parts", "PartOperations", "ExternalGroups", "Batches", "BatchOperations", "Schedule", "Suppliers"):
        schema_conn.execute('ALTER TABLE "' + table + '" ADD COLUMN private_legacy BLOB')
        schema_conn.execute('UPDATE "' + table + '" SET private_legacy=?', (b"\x00old\xff hidden",))
    schema_conn.commit()
    confirm_all(schema_conn, PARTS[0], person="real fixture recorder")
    confirm_all(schema_conn, PARTS[1])
    return schema_conn


def part_ref(conn, code=PARTS[0]):
    identity = WorkbenchIdentityRepository(conn).find_active("part", code)
    assert identity is not None
    return identity.ref


def create_part(conn, payload=None, *, key="part-action-create-0001", command=None, guard=None):
    service = WorkbenchProcessPartActionService(conn)
    payload = dict(CREATE if payload is None else payload)
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="part.create", context_ref="part-create-fixture",
        normalized_input=service.normalize_create(payload), guard=guard or (lambda: None),
        mutate=lambda _: service.create(payload))


def delete_parts(conn, preview, *, refs=None, scope=None, key="part-action-delete-0001", command=None, guard=None):
    request = preview.as_dict()["request"]
    refs = request["refs"] if refs is None else refs
    scope = request["scope"] if scope is None else scope
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="part.bulk_delete", context_ref="part-delete-fixture",
        normalized_input=preview.intent(), guard=guard or (lambda: preview),
        mutate=lambda checked: WorkbenchProcessPartActionService(conn).confirm_delete(checked, refs, scope=scope))


def storage(conn):
    return all_table_snapshot(conn)


def rows(conn, table):
    return [dict(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]


def assert_only_deleted(conn, before, deleted):
    schema, old = before
    current_schema, current = storage(conn)
    assert current_schema == schema
    changed = {"Parts", "PartOperations", "ExternalGroups", "WorkbenchEntityRefs", "WorkbenchCommandReceipts"}
    for table in old.keys() - changed:
        assert current[table] == old[table], table
    removed_refs = set()
    removed_ops, removed_groups = set(), set()
    for table in ("Parts", "PartOperations", "ExternalGroups"):
        columns = [row[1] for row in conn.execute('PRAGMA table_info("' + table + '")')]
        index = columns.index("part_no")
        assert current[table] == tuple(row for row in old[table] if row[index] not in deleted)
        if table == "PartOperations":
            removed_ops = {str(row[columns.index("id")]) for row in old[table] if row[index] in deleted}
        if table == "ExternalGroups":
            removed_groups = {row[columns.index("group_id")] for row in old[table] if row[index] in deleted}
    columns = [row[1] for row in conn.execute("PRAGMA table_info(WorkbenchEntityRefs)")]
    previous = {row[0]: dict(zip(columns, row)) for row in old["WorkbenchEntityRefs"]}
    for ref, value in previous.items():
        if value["active"] and value["entity_key"] in {
            "part": set(deleted), "template_operation": removed_ops, "template_external_group": removed_groups,
        }.get(value["kind"], set()):
            value.update(active=0, revision=value["revision"] + 1)
            removed_refs.add(ref)
    assert {row["ref"]: row for row in rows(conn, "WorkbenchEntityRefs")} == previous
    assert len(current["WorkbenchCommandReceipts"]) == len(old["WorkbenchCommandReceipts"]) + 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return removed_refs
