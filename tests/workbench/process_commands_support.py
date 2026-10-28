"""Real SQLite workflow/receipt fixtures, independent full-row preservation oracles."""

from __future__ import annotations

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_route_support import all_table_snapshot

PART = "PROC-001"
KEY = "process-command-00000001"


@pytest.fixture(name="stage_conn")
def stage_database(schema_conn):
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        seed_process(schema_conn)
    schema_conn.execute("ALTER TABLE PartOperations ADD COLUMN private_legacy TEXT")
    schema_conn.execute("UPDATE PartOperations SET private_legacy=' keep hidden ',created_at='2000-01-01 00:00:00'")
    schema_conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('PROC-S2','second',4.5)")
    schema_conn.execute("INSERT INTO WorkbenchSupplierOpTypes VALUES ('PROC-S2','PROC-EX')")
    schema_conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
        VALUES ('STAGE-OLD','PROC-B',10,'historical','internal',7,8)""")
    key = schema_conn.execute("SELECT id FROM BatchOperations WHERE op_code='STAGE-OLD'").fetchone()[0]
    schema_conn.execute("INSERT INTO Schedule(op_id,start_time,end_time) VALUES (?,?,?)", (key, "2026-10-01 08:00:00", "2026-10-01 09:00:00"))
    schema_conn.commit()
    return schema_conn


def identity_for(conn, part_no=PART):
    identity = WorkbenchIdentityRepository(conn).find_active("part", part_no)
    assert identity is not None
    return identity


def op_rows(conn, part_no=PART):
    return {row["seq"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations WHERE part_no=? ORDER BY seq", (part_no,))}


def group_rows(conn, part_no=PART):
    return {row["group_id"]: dict(row) for row in conn.execute("SELECT * FROM ExternalGroups WHERE part_no=? ORDER BY group_id", (part_no,))}


def op_ref(conn, seq=10, part_no=PART):
    row = conn.execute("SELECT id FROM PartOperations WHERE part_no=? AND seq=?", (part_no, seq)).fetchone()
    assert row is not None
    return ref_for(conn, "template_operation", str(row[0]))


def route_input(conn, text=None, part_no=PART):
    raw = conn.execute("SELECT route_raw FROM Parts WHERE part_no=?", (part_no,)).fetchone()[0] if text is None else text
    return {"route": {"mode": "text", "route_raw": raw}, "discard_group_refs": []}


def source_input(conn, part_no=PART):
    rows = active_rows_with_refs(conn, part_no)
    types = _fixture_refs(conn, "op_type", [row["op_type_id"] for row in rows if row["op_type_id"]])
    suppliers = _fixture_refs(conn, "supplier", [row["supplier_id"] for row in rows if row["supplier_id"]])
    return {"operations": [{"ref": row["ref"], "source": row["source"],
                            "op_type_ref": types[row["op_type_id"]] if row["op_type_id"] else None,
                            "supplier_ref": suppliers[row["supplier_id"]] if row["supplier_id"] else None,
                            "confirmed": True} for row in rows],
            "discard_group_refs": []}


def hours_input(conn, part_no=PART):
    operations, active_groups = [], set()
    for row in active_rows_with_refs(conn, part_no):
        fields = {"setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"]} if row["source"] == "internal" else {"external_days": row["ext_days"]}
        operations.append({"ref": row["ref"], **fields})
        active_groups.add(row["ext_group_id"])
    rows = {key: row for key, row in group_rows(conn, part_no).items() if key in active_groups and row["merge_mode"] == "merged"}
    refs = _fixture_refs(conn, "template_external_group", rows)
    groups = [{"ref": refs[key], "total_days": row["total_days"]} for key, row in rows.items()]
    return {"operations": operations, "groups": groups, "confirm_zero_unit_hours": True}


def active_rows_with_refs(conn, part_no):
    rows = conn.execute("""SELECT o.*,r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
        ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
        WHERE o.part_no=? AND o.status='active' ORDER BY o.seq""", (part_no,)).fetchall()
    assert all(row["ref"] is not None for row in rows)
    return rows


def _fixture_refs(conn, kind, keys):
    keys = set(keys)
    refs = WorkbenchIdentityRepository(conn).active_map(kind, keys)
    assert set(refs) == keys
    return {key: value.ref for key, value in refs.items()}


def run_stage(conn, action, payload, *, key=KEY):
    service = WorkbenchProcessMutationService(conn)
    identity = identity_for(conn)
    normalized = service.normalize(action, payload)
    reader = WorkbenchProcessQueryService(conn, part_ref=identity.ref)

    def guard():
        with reader.read_snapshot():
            facts = reader.facts()
            checked = service.checked_facts(reader.resolve(identity.ref), facts)
            return service.prepare_checked(action, normalized, checked, facts=facts)

    return WorkbenchCommandService(conn).execute(
        request_key=key, action="process." + action, context_ref=identity.ref,
        normalized_input=normalized, guard=guard,
        mutate=service.apply_prepared)


def prepare_stages(conn, *, source=True):
    run_stage(conn, "route_confirm", route_input(conn), key=KEY + "-route")
    if source:
        run_stage(conn, "source_confirm", source_input(conn), key=KEY + "-source")


def storage(conn):
    return all_table_snapshot(conn)
