"""Old identities and unavailable-vs-damaged ledger boundaries are explicit."""

import pytest

from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_execution_void_schema import install_execution_voids
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_operations import WorkbenchBatchOperationService
from core.services.workbench.batches import WorkbenchBatchService
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.batch_execution_ledger_support import batch_ledger_fixture, report
from tests.workbench.batch_execution_ledger_support import (
    legacy_batch_ledger as _legacy_batch_ledger,  # noqa: F401
)
from tests.workbench.batch_support import BASE, assert_error, batch_database, detail, list_data, post, ref_for, state

_batch_fixture = batch_database
_ledger_fixture = batch_ledger_fixture


def test_v24_no_ledger_is_explicit_read_only_legacy_mode(legacy_batch_ledger):
    case = legacy_batch_ledger
    before = state(case.client)
    case.conn.execute("PRAGMA query_only=ON")
    entity = detail(case.client)["data"]
    assert entity["execution_available"] is False
    assert entity["operations"][0]["execution"] is None
    assert entity["operations"][0]["execution_state"] is None
    assert entity["operations"][0]["data_quality"] == "unavailable"
    assert any(row["code"] == "execution_ledger_not_installed" for row in entity["issues"])
    assert state(case.client) == before


@pytest.mark.parametrize("damage", ["all_v25", "partial_v24", "clock_missing", "schema_changed", "index_missing"])
def test_damaged_ledger_never_falls_back_or_writes_on_get(request, damage):
    case = request.getfixturevalue("legacy_batch_ledger" if damage in ("all_v25", "partial_v24") else "batch_ledger")
    if damage == "partial_v24":
        case.conn.execute("BEGIN")
        install_execution_ledger(case.conn)
        install_execution_voids(case.conn)
        case.conn.commit()
    old_context = detail(case.client)["data"]["write_context"]
    if damage == "all_v25":
        case.conn.execute("UPDATE SchemaVersion SET version=25 WHERE id=1")
    elif damage == "partial_v24":
        case.conn.execute("DROP INDEX idx_wb_execution_reports_operation")
    elif damage == "clock_missing":
        case.conn.execute("DELETE FROM WorkbenchExecutionLedgerClock")
    elif damage == "schema_changed":
        case.conn.execute("ALTER TABLE WorkbenchProductionReports ADD COLUMN unexpected TEXT")
    else:
        case.conn.execute("DROP INDEX idx_wb_execution_reports_operation")
    case.conn.commit()
    before = state(case.client)
    case.conn.execute("PRAGMA query_only=ON")
    assert_error(case.client.get(BASE), "execution_ledger_unavailable")
    assert_error(case.client.get(BASE + "/" + case.batch_ref), "execution_ledger_unavailable")
    assert state(case.client) == before
    case.conn.execute("PRAGMA query_only=OFF")
    assert_error(post(case.client, "update", {"fields": {"remark": "blocked"}}, context=old_context), "execution_ledger_unavailable")
    assert state(case.client) == before


@pytest.mark.parametrize("kind", ["report", "legacy", "v24_legacy"])
@pytest.mark.parametrize("replace_batch", [False, True])
def test_old_same_number_instance_cannot_protect_or_complete_new_instance(request, kind, replace_batch):
    case = request.getfixturevalue("legacy_batch_ledger" if kind == "v24_legacy" else "batch_ledger")
    if kind == "report":
        report(case, 5)
    else:
        case.event(case.op_id, "start", version=7, batch_id="FREE-001")
        case.event(case.op_id, "finish", version=7, quantity=5, batch_id="FREE-001")
    old_ref = case.operation_ref
    old_events = [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    old_reports = [tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchProductionReports")] if kind != "v24_legacy" else []
    if kind != "report":
        # Simulate an old restored database whose writer bypassed FK protection.
        case.conn.execute("PRAGMA foreign_keys=OFF")
        case.conn.execute("DELETE FROM Schedule WHERE op_id=?", (case.op_id,))
    if replace_batch:
        if kind != "report":
            case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (case.op_id,))
        case.conn.execute("DELETE FROM Batches WHERE batch_id='FREE-001'")
        case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-001','P1',5)")
    else:
        case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (case.op_id,))
    case.conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source) VALUES (?,'FREE-001_01','FREE-001',1,'OT1','turning','internal')", (case.op_id,))
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=ON")
    entity = detail(case.client, ref_for(case.client))["data"]
    op = entity["operations"][0]
    assert op["operation_ref"] != old_ref and not op["completed"]
    assert not entity["protected"] and entity["relationships"]["execution_reference_count"] == 0
    if kind != "v24_legacy":
        assert op["execution"]["reports"] == [] and op["execution"]["legacy_facts"] == []
        assert op["execution"]["known_completed_quantity"] == 0
        assert [tuple(row) for row in case.conn.execute("SELECT * FROM WorkbenchProductionReports")] == old_reports
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")] == old_events
    assert post(case.client, "update", {"fields": {"quantity": 6}}).status_code == 200


def test_invalid_scope_keeps_protection_without_claiming_finished(batch_ledger):
    case = batch_ledger
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.event(case.op_id, "start", version=7, batch_id="FREE-001", role="critical_best")
    case.event(case.op_id, "finish", version=7, batch_id="FREE-001", role="critical_best", quantity=5)
    case.conn.execute("PRAGMA ignore_check_constraints=OFF")
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("DELETE FROM Schedule WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=ON")
    entity = detail(case.client)["data"]
    op = entity["operations"][0]
    assert entity["protected"] and op["data_quality"] == "invalid"
    assert not op["completed"] and op["execution"]["confirmed_finish"] is None
    before = state(case.client)
    for index, action in enumerate(("delete", "quantity", "sync")):
        def mutate(_):
            if action == "sync":
                return WorkbenchBatchOperationService(case.conn).sync(case.batch_ref, {})
            return WorkbenchBatchService(case.conn).apply("delete" if action == "delete" else "update",
                {} if action == "delete" else {"fields": {"quantity": 6}}, case.batch_ref)
        with pytest.raises(WorkbenchCommandRejected):
            WorkbenchCommandService(case.conn).execute(request_key=f"batch-invalid-guard-{index:02d}", action="batch.fixture",
                context_ref=case.batch_ref, normalized_input={}, guard=lambda: None, mutate=mutate)
        assert state(case.client) == before


def test_target_unknown_and_piece_one_are_kept_from_ledger(batch_ledger):
    case = batch_ledger
    case.conn.execute("UPDATE Batches SET quantity='unknown' WHERE batch_id='FREE-001'")
    case.conn.commit()
    op = detail(case.client)["data"]["operations"][0]
    assert op["execution"]["target_quantity"] is None and op["execution"]["remaining_quantity"] is None
    case.command("create", case.task(7, case.op_id), {"actual_start": "2026-09-09T08:00:00"})
    assert detail(case.client)["data"]["protected"]
    other = list_data(case.client)["data"]["entities"]
    piece = next(row for row in other if row["business_code"] == "B1")["operations"][0]["execution"]
    assert piece["target_basis"] == "piece" and piece["target_quantity"] == 1
