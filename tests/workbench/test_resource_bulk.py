"""Deletion keeps legacy authorization, calendar and domain reference protection."""

from unittest.mock import patch

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource_bulk import WorkbenchResourceBulkService
from tests.workbench.test_resource_file_support import (
    KINDS,
    confirm,
    raw,
    ref,
    resource_database,
    scope,
    seed_many,
    snapshot,
)


@pytest.mark.parametrize("kind", KINDS)
def test_explicit_cross_page_refs_deleted_only_through_domain(schema_conn, kind):
    refs = seed_many(schema_conn, kind, 3)
    service = WorkbenchResourceBulkService(schema_conn, kind)
    before, changes = snapshot(schema_conn), schema_conn.total_changes
    preview = service.preview_delete([refs[2], refs[0]], scope={"query": "FILE00001", **scope("internal" if kind == "op_type" else None)})
    assert preview.as_dict()["summary"]["delete"] == 2
    assert snapshot(schema_conn) == before and schema_conn.total_changes == changes
    original = type(service.adapter).apply
    with patch.object(type(service.adapter), "apply", autospec=True, side_effect=original) as calls:
        result = confirm(schema_conn, kind, preview)
    assert calls.call_count == 2
    assert [row["entity_ref"] for row in result["data"]["rows"]] == [refs[2], refs[0]]
    assert raw(schema_conn, kind, "FILE00001") is not None
    assert raw(schema_conn, kind, "FILE00000") is None


@pytest.mark.parametrize("kind,code", [("machine", "M1"), ("operator", "O1"), ("op_type", "OT1")])
def test_authorizations_and_domain_dependencies_prevent_bulk_delete(resource_conn, kind, code):
    service = WorkbenchResourceBulkService(resource_conn, kind)
    preview = service.preview_delete([ref(resource_conn, kind, code)], scope={})
    assert preview.as_dict()["summary"]["rejected"] == 1
    assert preview.as_dict()["rows"][0]["reference_count"] > 0
    before = snapshot(resource_conn)
    with patch.object(type(service.adapter), "apply", side_effect=AssertionError("must preflight whole batch")):
        with pytest.raises(WorkbenchCommandRejected):
            confirm(resource_conn, kind, preview)
    assert snapshot(resource_conn) == before


@pytest.mark.parametrize("kind", ("machine", "operator"))
def test_calendar_alone_blocks_cascading_deletion(schema_conn, kind):
    refs = seed_many(schema_conn, kind, 2)
    if kind == "machine":
        schema_conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time) VALUES ('FILE00001','2026-09-01 22:00','2026-09-02 06:00')")
    else:
        schema_conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_end) VALUES ('FILE00001','2026-09-01','22:00','06:00')")
    schema_conn.commit()
    preview = WorkbenchResourceBulkService(schema_conn, kind).preview_delete(refs, scope={})
    assert [row["result"] for row in preview.as_dict()["rows"]] == ["delete", "rejected"]
    before = snapshot(schema_conn)
    with pytest.raises(WorkbenchCommandRejected):
        confirm(schema_conn, kind, preview)
    assert snapshot(schema_conn) == before


def test_foreign_kind_category_and_duplicate_refs_rejected(resource_conn):
    service = WorkbenchResourceBulkService(resource_conn, "op_type")
    refs = [ref(resource_conn, "machine", "M1"), ref(resource_conn, "op_type", "EXT")]
    preview = service.preview_delete(refs, scope=scope("internal"))
    assert preview.as_dict()["summary"]["rejected"] == 2
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        service.preview_delete([refs[1], refs[1]], scope={})


@pytest.mark.parametrize("mutation", ("hidden", "authorization", "calendar", "recreate"))
def test_last_row_change_invalidates_whole_original_preview(schema_conn, mutation):
    refs = seed_many(schema_conn, "machine", 2)
    service = WorkbenchResourceBulkService(schema_conn, "machine")
    preview = service.preview_delete(refs, scope={})
    if mutation == "hidden":
        schema_conn.execute("UPDATE Machines SET created_at='old change' WHERE machine_id='FILE00001'")
    elif mutation == "calendar":
        schema_conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time) VALUES ('FILE00001','2026-09-01','2026-09-02')")
    elif mutation == "authorization":
        schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O','operator')")
        schema_conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O','FILE00001')")
    else:
        schema_conn.execute("DELETE FROM Machines WHERE machine_id='FILE00001'")
        schema_conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('FILE00001','new instance')")
    schema_conn.commit()
    before = snapshot(schema_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        confirm(schema_conn, "machine", preview)
    assert error.value.code == "stale_write" and snapshot(schema_conn) == before


def test_late_domain_failure_rolls_back_even_if_outer_caller_catches(schema_conn):
    refs = seed_many(schema_conn, "machine", 3)
    service = WorkbenchResourceBulkService(schema_conn, "machine")
    preview = service.preview_delete(refs, scope={})
    original = service.adapter.apply
    def fail(action, payload, identity):
        result = original(action, payload, identity)
        if identity.ref == refs[-1]:
            raise RuntimeError("after final delete")
        return result
    before = snapshot(schema_conn)
    with patch.object(service.adapter, "apply", fail):
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            with pytest.raises(RuntimeError):
                service.confirm_delete(preview, refs, scope={})
            assert snapshot(schema_conn) == before
    assert snapshot(schema_conn) == before


def test_receipt_failure_rolls_back_and_replay_precedes_preview(schema_conn):
    refs = seed_many(schema_conn, "supplier", 2)
    preview = WorkbenchResourceBulkService(schema_conn, "supplier").preview_delete(refs, scope={})
    command = WorkbenchCommandService(schema_conn)
    before = snapshot(schema_conn)
    command.repo.insert = lambda **_: (_ for _ in ()).throw(RuntimeError("receipt failure"))
    with pytest.raises(WorkbenchCommandUncertain):
        confirm(schema_conn, "supplier", preview, command=command)
    assert snapshot(schema_conn) == before
    first = confirm(schema_conn, "supplier", preview, key="resource-bulk-replay")
    replay = confirm(schema_conn, "supplier", preview, key="resource-bulk-replay", guard=lambda: pytest.fail("must replay before expired guard"))
    assert replay == {**first, "replayed": True}
