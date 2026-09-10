"""Part creation, immutable delete preflight, atomic receipts and preservation."""

import sqlite3
from unittest.mock import patch

import pytest

from core.errors import BusinessError, ValidationError
from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_process_route import MAX_ROUTE_TEXT_BYTES
from core.models.workbench_resource_action import ResourceActionPreview, public_action_row
from core.services.process.part_service import PartService
from core.services.process.workflow_state import read_workflow, require_template_ready
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from tests.workbench.process_part_actions_support import (
    CREATE,
    PARTS,
    assert_only_deleted,
    create_part,
    delete_parts,
    part_actions_database,
    part_ref,
    rows,
    storage,
)


@pytest.mark.parametrize("route", [None, "", "  \r\n  ", CREATE["route_raw"], "not a parseable route"])
def test_create_preserves_route_without_parse_hours_or_confirmation(part_actions_conn, route):
    conn = part_actions_conn
    before = storage(conn)
    payload = {**CREATE, "business_code": " NEW-001 ", "label": " new part ", "route_raw": route}
    original = PartService.create
    with patch.object(PartService, "create", autospec=True, side_effect=original) as create_call:
        with patch.object(PartService, "reparse_and_save", side_effect=AssertionError("no auto parse")):
            with patch.object(PartService, "_parse_route_or_raise", side_effect=AssertionError("no strict parse")):
                result = create_part(conn, payload)
    assert create_call.call_count == 1
    assert create_call.call_args.kwargs.get("route_raw") is None
    assert create_call.call_args.args[1:] == ("NEW-001", "new part")
    row = dict(conn.execute("SELECT * FROM Parts WHERE part_no='NEW-001'").fetchone())
    assert (row["part_name"], row["route_raw"], row["route_parsed"], row["remark"]) == ("new part", route, "no", "note")
    assert result["data"]["entity_ref"] == part_ref(conn, "NEW-001")
    workflow = read_workflow(conn, "NEW-001")
    assert workflow == result["data"]["workflow"]
    assert workflow["origin"] == "managed" and workflow["stage"] == "route" and not workflow["ready"]
    record = conn.execute("SELECT * FROM WorkbenchProcessWorkflow WHERE part_ref=?", (part_ref(conn, "NEW-001"),)).fetchone()
    assert all(value is None for value in tuple(record)[1:])
    with pytest.raises(BusinessError, match="尚未完成"):
        require_template_ready(conn, "NEW-001")
    changed = {"Parts", "WorkbenchEntityRefs", "WorkbenchProcessWorkflow", "WorkbenchCommandReceipts"}
    assert storage(conn)[0] == before[0]
    for table in before[1].keys() - changed:
        assert storage(conn)[1][table] == before[1][table], table
    for table in ("Parts", "WorkbenchEntityRefs", "WorkbenchProcessWorkflow"):
        assert storage(conn)[1][table][:-1] == before[1][table], table


def test_create_omitted_nullable_fields_stay_null(schema_conn):
    result = create_part(schema_conn, {"business_code": "0", "label": "0"})
    row = schema_conn.execute("SELECT route_raw,remark FROM Parts WHERE part_no='0'").fetchone()
    assert tuple(row) == (None, None) and result["result"] == "committed"


@pytest.mark.parametrize("field", ["business_code", "label"])
@pytest.mark.parametrize("value", [None, "", " \n\t "])
def test_required_create_fields_reject_empty(schema_conn, field, value):
    before = storage(schema_conn)
    with pytest.raises(ValidationError):
        create_part(schema_conn, {**CREATE, field: value})
    assert storage(schema_conn) == before


@pytest.mark.parametrize("field", ["business_code", "label", "route_raw", "remark"])
@pytest.mark.parametrize("value", [False, 1, 1.5, [], {}, b"text", "\ud800"])
def test_create_rejects_nontext_and_invalid_characters(schema_conn, field, value):
    before = storage(schema_conn)
    with pytest.raises((ValidationError, WorkbenchCommandRejected)):
        create_part(schema_conn, {**CREATE, field: value})
    assert storage(schema_conn) == before


@pytest.mark.parametrize("payload", [None, [], "part", {}, {**CREATE, "route_parsed": "yes"}, {**CREATE, "fields": {}},
                                    {**CREATE, "strict_mode": True}, {**CREATE, "confirmed_by": "guessed"}])
def test_create_shape_is_strict(schema_conn, payload):
    before = storage(schema_conn)
    with pytest.raises(ValidationError):
        WorkbenchProcessPartActionService.normalize_create(payload)
    assert storage(schema_conn) == before


def test_create_route_size_is_utf8_bytes_without_truncation(schema_conn):
    text = "a" * MAX_ROUTE_TEXT_BYTES
    assert WorkbenchProcessPartActionService.normalize_create({**CREATE, "route_raw": text})["route_raw"] == text
    for text in (text + "a", "路" * (MAX_ROUTE_TEXT_BYTES // 3 + 1)):
        before = storage(schema_conn)
        with pytest.raises(WorkbenchCommandRejected) as error:
            create_part(schema_conn, {**CREATE, "route_raw": text})
        assert error.value.status == 413 and storage(schema_conn) == before


def test_duplicate_create_uses_domain_validation_and_preserves_all(part_actions_conn):
    conn = part_actions_conn
    before = storage(conn)
    with pytest.raises(BusinessError, match="已存在"):
        create_part(conn, {**CREATE, "business_code": " DROP-A "})
    assert storage(conn) == before


def test_mutations_require_outer_transaction_and_leave_no_pending_writes(schema_conn):
    service = WorkbenchProcessPartActionService(schema_conn)
    with pytest.raises(RuntimeError, match="外层"):
        service.create(CREATE)
    with pytest.raises(RuntimeError, match="外层"):
        service.confirm_delete(None, ["f" * 48], scope={})
    assert not schema_conn.in_transaction and not rows(schema_conn, "Parts")


def test_create_savepoint_and_outer_rollback_restore_every_table(schema_conn):
    conn, service = schema_conn, WorkbenchProcessPartActionService(schema_conn)
    before = storage(conn)
    with TransactionManager(conn).transaction(begin_immediate=True):
        with patch("core.services.workbench.process_part_actions.start_workflow", side_effect=RuntimeError("fixture failure")):
            with pytest.raises(WorkbenchCommandRejected, match="本次未保存"):
                service.create(CREATE)
        assert storage(conn) == before and conn.in_transaction
    with pytest.raises(RuntimeError, match="outer rollback"):
        with TransactionManager(conn).transaction(begin_immediate=True):
            service.create(CREATE)
            assert conn.in_transaction and not rows(conn, "WorkbenchCommandReceipts")
            raise RuntimeError("outer rollback")
    assert storage(conn) == before


@pytest.mark.parametrize("action", ["create", "delete"])
def test_receipt_failure_rolls_back_and_retry_replays_before_guard(part_actions_conn, action):
    conn, command = part_actions_conn, WorkbenchCommandService(part_actions_conn)
    preview = WorkbenchProcessPartActionService(conn).preview_delete([part_ref(conn)], scope={})
    def run(**kwargs):
        return create_part(conn, **kwargs) if action == "create" else delete_parts(conn, preview, **kwargs)
    before = storage(conn)
    with patch.object(command.repo, "insert", side_effect=RuntimeError("receipt failure")):
        with pytest.raises(WorkbenchCommandUncertain):
            run(command=command)
    assert storage(conn) == before
    first = run()
    after = storage(conn)
    replay = run(guard=lambda: pytest.fail("must replay before guard"))
    assert replay == {**first, "replayed": True} and storage(conn) == after


def test_delete_preview_is_readonly_detached_and_complete(part_actions_conn):
    conn = part_actions_conn
    service = WorkbenchProcessPartActionService(conn)
    refs = [part_ref(conn, code) for code in reversed(PARTS)]
    before, changes = storage(conn), conn.total_changes
    preview = service.preview_delete(refs, scope={"query": "does not match selected rows", "stage": "route"})
    assert isinstance(preview, ResourceActionPreview) and preview.as_dict()["commit_policy"] == "atomic"
    assert preview.as_dict()["summary"]["delete"] == 2
    assert [row["entity_ref"] for row in preview.as_dict()["rows"]] == refs
    row = preview.as_dict()["rows"][1]
    assert row["before"]["operation_count"] == 4 and row["before"]["external_group_count"] == 2
    assert len(row["expected"]["confirmations"]) == 6
    assert row["expected"]["operations"][0]["private_legacy"]["hex"] == b"\x00old\xff hidden".hex()
    assert "expected" not in public_action_row(row)
    detached = preview.as_dict()
    detached["rows"].clear()
    refs.clear()
    assert len(preview.as_dict()["rows"]) == 2
    assert storage(conn) == before and conn.total_changes == changes and not conn.in_transaction


@pytest.mark.parametrize("count", [1, 2])
def test_delete_exact_selection_and_complete_groups_preserves_all_other_rows(part_actions_conn, count):
    conn = part_actions_conn
    selected = PARTS[:count]
    refs = [part_ref(conn, code) for code in selected]
    preview = WorkbenchProcessPartActionService(conn).preview_delete(refs, scope={"query": "DROP"})
    before = storage(conn)
    original = PartService.delete
    with patch.object(PartService, "delete", autospec=True, side_effect=original) as calls:
        result = delete_parts(conn, preview)
    assert calls.call_count == count and result["data"]["deleted_count"] == count
    assert [row["entity_ref"] for row in result["data"]["rows"]] == refs
    retired = assert_only_deleted(conn, before, selected)
    assert len(retired) == (7 if count == 1 else 13)


def test_batch_reference_rejects_whole_selection_before_any_delete(part_actions_conn):
    conn = part_actions_conn
    preview = WorkbenchProcessPartActionService(conn).preview_delete([part_ref(conn), part_ref(conn, "P1")], scope={})
    assert [row["result"] for row in preview.as_dict()["rows"]] == ["delete", "rejected"]
    assert preview.as_dict()["rows"][1]["reference_count"] == 1
    before = storage(conn)
    with patch.object(PartService, "delete", side_effect=AssertionError("must preflight entire batch")):
        with pytest.raises(WorkbenchCommandRejected) as error:
            delete_parts(conn, preview)
    assert error.value.code == "constraint_conflict" and storage(conn) == before


@pytest.mark.parametrize("value", [None, [], (), "x" * 48, [None], [False], [123], ["DROP-A"], ["g" * 48]])
def test_bad_refs_fail_without_writes(part_actions_conn, value):
    before = storage(part_actions_conn)
    with pytest.raises(ValidationError):
        WorkbenchProcessPartActionService(part_actions_conn).preview_delete(value, scope={})
    assert storage(part_actions_conn) == before


def test_duplicate_missing_wrong_kind_and_inactive_refs_are_not_dropped(part_actions_conn):
    conn = part_actions_conn
    service = WorkbenchProcessPartActionService(conn)
    ref = part_ref(conn)
    with pytest.raises(ValidationError):
        service.preview_delete([ref, ref], scope={})
    supplier_ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='supplier' LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES('RETIRED','retired')")
    retired = part_ref(conn, "RETIRED")
    conn.execute("DELETE FROM Parts WHERE part_no='RETIRED'")
    conn.commit()
    preview = service.preview_delete([ref, "f" * 48, supplier_ref, retired], scope={})
    assert [row["result"] for row in preview.as_dict()["rows"]] == ["delete", "rejected", "rejected", "rejected"]
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected):
        delete_parts(conn, preview)
    assert storage(conn) == before


@pytest.mark.parametrize("scope", [None, [], {"number": 1}, {"size": 20}, {"kind": "part"}, {"query": 1},
                                   {"query": "x" * 201}, {"stage": "bad"}, {"sort": "bad"}, {"direction": "bad"}])
def test_delete_scope_strict_without_pagination(part_actions_conn, scope):
    before = storage(part_actions_conn)
    with pytest.raises((ValidationError, WorkbenchCommandRejected)):
        WorkbenchProcessPartActionService(part_actions_conn).preview_delete([part_ref(part_actions_conn)], scope=scope)
    assert storage(part_actions_conn) == before


@pytest.mark.parametrize("change", ["part", "operation", "group", "deleted_operation", "workflow", "confirmation", "batch", "identity"])
def test_current_full_facts_invalidate_old_preview(part_actions_conn, change):
    conn = part_actions_conn
    ref = part_ref(conn, PARTS[1])
    preview = WorkbenchProcessPartActionService(conn).preview_delete([part_ref(conn), ref], scope={})
    sql = {
        "part": "UPDATE Parts SET private_legacy='changed' WHERE part_no='DROP-B'",
        "operation": "UPDATE PartOperations SET private_legacy='changed' WHERE part_no='DROP-B' AND seq=1",
        "deleted_operation": "UPDATE PartOperations SET private_legacy='changed' WHERE part_no='DROP-B' AND status='deleted'",
        "group": "UPDATE ExternalGroups SET total_days=99,private_legacy='changed' WHERE part_no='DROP-B'",
        "workflow": "UPDATE WorkbenchProcessWorkflow SET route_confirmed_by='new person' WHERE part_ref=?",
        "confirmation": "UPDATE WorkbenchProcessOperationConfirmations SET confirmed_by='new person' WHERE part_ref=?",
        "batch": "INSERT INTO Batches(batch_id,part_no,quantity) VALUES('NEW-BATCH','DROP-B',1)",
        "identity": "UPDATE WorkbenchEntityRefs SET revision=revision+1 WHERE ref=?",
    }[change]
    conn.execute(sql, (ref,) if "?" in sql else ())
    conn.commit()
    before = storage(conn)
    with patch.object(PartService, "delete", side_effect=AssertionError("must recheck first")):
        with pytest.raises(WorkbenchCommandRejected) as error:
            delete_parts(conn, preview)
    assert error.value.code == "stale_write" and storage(conn) == before


@pytest.mark.parametrize("change", ["order", "scope", "invalid", "omit", "expand"])
def test_changed_request_never_retargets_delete(part_actions_conn, change):
    conn = part_actions_conn
    refs = [part_ref(conn, code) for code in PARTS]
    preview = WorkbenchProcessPartActionService(conn).preview_delete(refs, scope={})
    kwargs = {"order": {"refs": list(reversed(refs))}, "scope": {"scope": {"query": "DROP"}},
              "invalid": {"refs": ["DROP-A"]}, "omit": {"refs": refs[:1]},
              "expand": {"refs": refs + [part_ref(conn, "P1")]}}[change]
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        delete_parts(conn, preview, **kwargs)
    assert error.value.code == "stale_write" and storage(conn) == before


def test_same_code_recreation_keeps_old_tombstone_and_history(part_actions_conn):
    conn = part_actions_conn
    old_ref = part_ref(conn)
    service = WorkbenchProcessPartActionService(conn)
    old_preview = service.preview_delete([old_ref], scope={})
    history = (rows(conn, "WorkbenchProcessWorkflow"), rows(conn, "WorkbenchProcessOperationConfirmations"))
    delete_parts(conn, old_preview)
    result = create_part(conn, {**CREATE, "business_code": PARTS[0]})
    assert result["data"]["entity_ref"] != old_ref
    assert rows(conn, "WorkbenchProcessWorkflow")[:-1] == history[0]
    assert rows(conn, "WorkbenchProcessOperationConfirmations") == history[1]
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        delete_parts(conn, old_preview, key="part-action-delete-recreated")
    assert error.value.code == "stale_write" and storage(conn) == before
    assert service.preview_delete([old_ref], scope={}).as_dict()["summary"]["rejected"] == 1


def test_last_delete_failure_rolls_back_even_when_outer_catches(part_actions_conn):
    conn = part_actions_conn
    service = WorkbenchProcessPartActionService(conn)
    refs = [part_ref(conn, code) for code in PARTS]
    preview = service.preview_delete(refs, scope={})
    original = service.domain.delete
    def fail_last(code):
        original(code)
        if code == PARTS[-1]:
            raise RuntimeError("after final delete")
    before = storage(conn)
    with patch.object(service.domain, "delete", side_effect=fail_last):
        with TransactionManager(conn).transaction(begin_immediate=True):
            with pytest.raises(RuntimeError, match="after final"):
                service.confirm_delete(preview, refs, scope={})
            assert storage(conn) == before and conn.in_transaction
    assert storage(conn) == before


def test_foreign_group_member_and_whitespace_code_block_without_guessing(part_actions_conn):
    conn = part_actions_conn
    conn.execute("UPDATE PartOperations SET ext_group_id='DROP-A-G' WHERE part_no='DROP-B' AND seq=3")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES(' DROP-A ','legacy whitespace')")
    conn.commit()
    service = WorkbenchProcessPartActionService(conn)
    preview = service.preview_delete([part_ref(conn), part_ref(conn, " DROP-A ")], scope={})
    assert preview.as_dict()["summary"]["rejected"] == 2
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected):
        delete_parts(conn, preview)
    assert storage(conn) == before


@pytest.mark.parametrize("broken", ["foreign_keys", "identity_trigger", "missing_identity"])
def test_broken_storage_fails_closed_without_repair(part_actions_conn, broken):
    conn = part_actions_conn
    if broken == "foreign_keys":
        conn.execute("PRAGMA foreign_keys=OFF")
    elif broken == "identity_trigger":
        conn.execute("DROP TRIGGER wb_ref_template_operation_delete")
    else:
        conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='template_operation' AND entity_key=(SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no='DROP-A' AND seq=1)")
    conn.commit()
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchProcessPartActionService(conn).preview_delete([part_ref(conn)], scope={})
    assert error.value.code == "storage_failure" and storage(conn) == before


def test_other_connection_change_rejects_previous_preview(part_actions_conn, tmp_path):
    path = str(tmp_path / "part-delete-race.db")
    with sqlite3.connect(path) as setup:
        part_actions_conn.backup(setup)
    conn, other = sqlite3.connect(path), sqlite3.connect(path)
    try:
        conn.row_factory = other.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        other.execute("PRAGMA foreign_keys=ON")
        preview = WorkbenchProcessPartActionService(conn).preview_delete([part_ref(conn)], scope={})
        other.execute("UPDATE ExternalGroups SET remark='concurrent change' WHERE part_no='DROP-A'")
        other.commit()
        before = storage(conn)
        with pytest.raises(WorkbenchCommandRejected) as error:
            delete_parts(conn, preview)
        assert error.value.code == "stale_write" and storage(conn) == before
    finally:
        other.close()
        conn.close()


def test_bulk_selection_beyond_page_and_import_limit_is_not_truncated(schema_conn):
    conn = schema_conn
    count = 2001
    conn.executemany("INSERT INTO Parts(part_no,part_name) VALUES(?,?)",
                     [("MANY-" + str(index), "unlinked") for index in range(count + 1)])
    conn.commit()
    refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' ORDER BY entity_key")]
    selected, survivor = refs[:count], refs[count]
    preview = WorkbenchProcessPartActionService(conn).preview_delete(selected, scope={})
    assert preview.as_dict()["request"]["refs"] == selected
    assert preview.as_dict()["summary"]["delete"] == count
    result = delete_parts(conn, preview)
    assert [row["entity_ref"] for row in result["data"]["rows"]] == selected
    assert result["data"]["deleted_count"] == count
    assert len(rows(conn, "Parts")) == 1
    assert conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND active=1").fetchone()[0] == survivor


def test_typed_connection_preserves_dates_hidden_blobs_and_nonfinite_old_hours(part_actions_conn):
    conn = get_connection(":memory:")
    try:
        part_actions_conn.backup(conn)
        conn.execute("UPDATE PartOperations SET unit_hours=? WHERE part_no='DROP-A' AND status='deleted'", (float("inf"),))
        conn.commit()
        before = storage(conn)
        service = WorkbenchProcessPartActionService(conn)
        blocked = service.preview_delete([part_ref(conn, "P1")], scope={})
        assert blocked.as_dict()["rows"][0]["expected"]["batches"][0]["due_date"] == {
            "storage_type": "date", "iso": "2026-10-01"}
        preview = service.preview_delete([part_ref(conn)], scope={})
        fact = preview.as_dict()["rows"][0]["expected"]
        assert fact["part"]["created_at"] == conn.execute("SELECT created_at FROM Parts WHERE part_no='DROP-A'").fetchone()[0]
        assert fact["operations"][-1]["unit_hours"] == {"storage_type": "float", "value": "inf"}
        delete_parts(conn, preview)
        assert_only_deleted(conn, before, [PARTS[0]])
    finally:
        conn.close()


def test_inner_create_and_delete_are_invisible_before_outer_commit(part_actions_conn, tmp_path):
    path = str(tmp_path / "part-uncommitted.db")
    with sqlite3.connect(path) as setup:
        part_actions_conn.backup(setup)
    conn, observer = sqlite3.connect(path), sqlite3.connect(path)
    try:
        conn.row_factory = observer.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        service = WorkbenchProcessPartActionService(conn)
        refs = [part_ref(conn)]
        preview = service.preview_delete(refs, scope={})
        before = storage(observer)
        with pytest.raises(RuntimeError, match="outer rollback"):
            with TransactionManager(conn).transaction(begin_immediate=True):
                service.create(CREATE)
                service.confirm_delete(preview, refs, scope={})
                assert storage(observer) == before
                assert conn.in_transaction and not rows(conn, "WorkbenchCommandReceipts")
                raise RuntimeError("outer rollback")
        assert storage(conn) == storage(observer) == before
    finally:
        observer.close()
        conn.close()
