"""Preserving route writes, complete group acknowledgements and savepoint failure."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.part_service import PartService
from core.services.process.workflow_state import operation_confirmations, read_workflow
from core.services.workbench.process_file_route import ProcessRouteFileOperations
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_file_route_support import (
    HIDDEN,
    PART,
    ROUTE,
    apply,
    decoded,
    fail_if_called,
    file_rows,
    groups,
    operations,
    ref,
    review,
    route_file_database,
    snapshot,
    table,
)

_fixture = route_file_database


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_new_parts_use_create_owner_pending_or_route_only_confirmation(route_file_conn, monkeypatch, fmt):
    conn = route_file_conn
    raw = " 10车削 ; 20热处理\n30unknown "
    source = file_rows([{"business_code": "NEW-ROUTE", "label": " new part ", "route_raw": raw, "remark": " note "},
                        {"business_code": "PENDING", "label": "no route yet"}], fmt)
    calls, original = [], WorkbenchProcessPartActionService.create

    def create(service, payload):
        calls.append(dict(payload))
        return original(service, payload)

    monkeypatch.setattr(WorkbenchProcessPartActionService, "create", create)
    monkeypatch.setattr(PartService, "reparse_and_save", fail_if_called)
    before_operations, before_groups = operations(conn), groups(conn)
    before_confirmations = table(conn, "WorkbenchProcessOperationConfirmations")
    rows, _ = review(conn, source)
    assert rows[1]["route_summary"] is None
    results, refs = apply(conn, rows)
    assert len(calls) == 2 and calls[0] == rows[0]["input"] and calls[1] == rows[1]["input"]
    assert refs == sorted(row["entity_ref"] for row in results) and all(row["result"] == "committed" for row in results)
    assert all(set(row) == {"row", "result", "entity_ref", "business_code"} for row in results)
    assert conn.execute("SELECT part_name,route_raw,route_parsed,remark FROM Parts WHERE part_no='NEW-ROUTE'").fetchone()[:] == ("new part", raw, "yes", "note")
    state = read_workflow(conn, "NEW-ROUTE")
    assert state["route"]["state"] == "confirmed" and state["route"]["confirmed_by"] is None
    assert state["source"]["state"] == "unconfirmed" and state["hours"]["state"] == "locked" and not state["ready"]
    pending = read_workflow(conn, "PENDING")
    assert pending["origin"] == "managed" and pending["route"]["state"] == "missing" and operations(conn, "PENDING") == {}
    new = operations(conn, "NEW-ROUTE")
    assert new[10]["source"] == "internal" and new[20]["supplier_id"] == "PROC-S" and new[20]["ext_days"] == 3.25
    assert all(row["setup_hours"] is None and row["unit_hours"] is None for row in new.values())
    assert all(new[30][field] is None for field in ("source", "op_type_id", "supplier_id", "ext_days"))
    assert groups(conn, "NEW-ROUTE") == {} and table(conn, "WorkbenchProcessOperationConfirmations") == before_confirmations
    assert operations(conn) == before_operations and groups(conn) == before_groups


def test_text_only_update_preserves_all_hidden_facts_and_confirmations(route_file_conn, monkeypatch):
    conn = route_file_conn
    monkeypatch.setattr(PartService, "reparse_and_save", fail_if_called)
    monkeypatch.setattr("core.services.workbench.process_file_route.record_confirmation", fail_if_called)
    before = snapshot(conn)
    before_parts = table(conn, "Parts")
    rows, _ = review(conn, decoded({"business_code": PART, "label": "new name", "remark": None, "route_raw": ROUTE}))
    apply(conn, rows)
    after = snapshot(conn)
    assert before[0] == after[0]
    for name in before[1].keys() - {"Parts", "WorkbenchEntityRefs"}:
        assert before[1][name] == after[1][name], name
    previous = {row["part_no"]: row for row in before_parts}
    for row in table(conn, "Parts"):
        old = previous[row["part_no"]]
        if row["part_no"] == PART:
            assert row == {**old, "part_name": "new name", "remark": None, "updated_at": row["updated_at"]}
            assert row["route_file_private"] == HIDDEN
        else:
            assert row == old
    assert read_workflow(conn, PART)["ready"]


def test_unchanged_export_preserves_legacy_padded_label_and_remark(route_file_conn):
    conn = route_file_conn
    conn.execute("UPDATE Parts SET part_name='  original name  ',remark='  original remark  ' WHERE part_no=?", (PART,))
    conn.commit()
    before = snapshot(conn)
    rows, _ = review(conn, decoded({"business_code": PART, "label": "  original name  ", "remark": "  original remark  "}))
    assert rows[0]["result"] == "unchanged"
    apply(conn, rows)
    assert snapshot(conn) == before


def test_route_diff_retains_ids_refs_choices_and_hidden_fields_only_changes_intended_fields(route_file_conn):
    conn = route_file_conn
    before = snapshot(conn)
    old_ops, old_groups = operations(conn), groups(conn)
    old_refs = {seq: ref(conn, "template_operation", row["id"]) for seq, row in old_ops.items()}
    old_confirmations = operation_confirmations(conn, PART)
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": "10renamed20热处理40unknown"}))
    assert extra["affected_groups"] == []
    apply(conn, rows)
    current = operations(conn)
    assert current[10] == {**old_ops[10], "op_type_name": "renamed"}
    assert current[20] == old_ops[20]
    assert current[30] == {**old_ops[30], "status": "deleted"}
    assert all(current[40][key] is None for key in ("source", "op_type_id", "supplier_id", "ext_days", "setup_hours", "unit_hours"))
    assert groups(conn) == old_groups
    assert old_refs == {seq: ref(conn, "template_operation", row["id"]) for seq, row in old_ops.items()}
    after = snapshot(conn)
    allowed = {"Parts", "PartOperations", "WorkbenchEntityRefs", "WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations", "sqlite_sequence"}
    for name in before[1].keys() - allowed:
        assert before[1][name] == after[1][name], name
    current_confirmations = operation_confirmations(conn, PART)
    assert current_confirmations[old_refs[20]] == old_confirmations[old_refs[20]]
    assert current_confirmations[old_refs[10]]["source"]["state"] == "unconfirmed"
    state = read_workflow(conn, PART)
    assert state["route"]["state"] == "confirmed" and state["source"]["state"] == "unconfirmed"


def test_restoring_deleted_sequence_retains_row_and_ref_but_does_not_revive_confirmations(route_file_conn):
    conn = route_file_conn
    original, op_ref = operations(conn)[30], ref(conn, "template_operation", operations(conn)[30]["id"])
    rows, _ = review(conn, decoded({"business_code": PART, "route_raw": "10车削20热处理"}))
    apply(conn, rows)
    rows, _ = review(conn, decoded({"business_code": PART, "route_raw": ROUTE}))
    apply(conn, rows)
    assert operations(conn)[30] == original and ref(conn, "template_operation", original["id"]) == op_ref
    assert operation_confirmations(conn, PART)[op_ref]["source"]["state"] == "unconfirmed"
    assert not read_workflow(conn, PART)["ready"]


@pytest.mark.parametrize("change", ["remove", "rename", "insert_in_range", "restore", "linked_outside_range"])
def test_affected_groups_are_complete_projected_rules_and_only_exact_ack_allows_change(route_file_conn, change):
    conn = route_file_conn
    if change in ("insert_in_range", "restore"):
        conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE group_id='PROC-G'")
    if change == "restore":
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,ext_group_id) VALUES ('PROC-001',25,'retained','external','deleted','PROC-G')")
    if change == "linked_outside_range":
        conn.execute("UPDATE ExternalGroups SET start_seq=21,end_seq=25 WHERE group_id='PROC-G'")
    conn.commit()
    raw = {"remove": "10车削30检验", "rename": "10车削20renamed30检验", "insert_in_range": "10车削20热处理25added30检验",
           "restore": "10车削20热处理25retained30检验", "linked_outside_range": "10车削20renamed30检验"}[change]
    before = snapshot(conn)
    old_ops, old_groups = operations(conn), groups(conn)
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": raw}))
    group_ref = ref(conn, "template_external_group", "PROC-G")
    assert len(extra["affected_groups"]) == 1
    group = extra["affected_groups"][0]
    assert group["ref"] == group_ref and group["business_code"] == PART and group["part_ref"] == ref(conn)
    assert group["remark"] == "保留合并规则" and group["total_days"] == 6.75 and group["merge_mode"] == "merged"
    assert not {"group_id", "part_no", "revision", "route_file_private"} & group.keys()
    for ack in ([], ["a" * 48], [group_ref, "a" * 48], [group_ref, group_ref]):
        with pytest.raises(WorkbenchCommandRejected) as caught:
            apply(conn, rows, ack)
        assert caught.value.code == "group_discard_required" and snapshot(conn) == before
    results, affected = apply(conn, rows, [group_ref])
    assert affected == [ref(conn)] and results[0]["result"] == "committed"
    assert groups(conn) == {"UNUSED": old_groups["UNUSED"]}
    expected = {**old_ops[20], "ext_group_id": None}
    if change == "remove":
        expected["status"] = "deleted"
    if change in ("rename", "linked_outside_range"):
        expected["op_type_name"] = "renamed"
    assert operations(conn)[20] == expected
    assert conn.execute("SELECT active FROM WorkbenchEntityRefs WHERE ref=?", (group_ref,)).fetchone()[0] == 0


def test_new_adjacent_operations_never_discard_unaffected_group(route_file_conn):
    conn = route_file_conn
    old_groups, old_ops = groups(conn), operations(conn)
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": "10车削15热处理20热处理30检验40热处理"}))
    assert extra["affected_groups"] == []
    before = snapshot(conn)
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows, [ref(conn, "template_external_group", "PROC-G")])
    assert snapshot(conn) == before
    apply(conn, rows)
    assert groups(conn) == old_groups
    assert {seq: row for seq, row in operations(conn).items() if seq in old_ops} == old_ops
    assert operations(conn)[15]["ext_group_id"] is None and operations(conn)[40]["ext_group_id"] is None


def test_ack_must_cover_groups_across_all_file_parts(route_file_conn):
    conn = route_file_conn
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days) VALUES ('OTHER-G','PROC-003',10,10,'merged',2)")
    conn.execute("UPDATE PartOperations SET ext_group_id='OTHER-G' WHERE part_no='PROC-003'")
    conn.commit()
    before = snapshot(conn)
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": "10车削20rename30检验"},
                                     {"business_code": "PROC-003", "route_raw": "10other"}))
    ack = [group["ref"] for group in extra["affected_groups"]]
    assert len(ack) == 2
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows, ack[:1])
    assert snapshot(conn) == before
    results, affected = apply(conn, rows, ack)
    assert affected == sorted(row["entity_ref"] for row in results) and len(set(affected)) == 2


@pytest.mark.parametrize("damage", ["foreign_group", "cross_part_member", "bad_range", "bad_status", "bad_sequence"])
def test_broken_legacy_template_is_rejected_without_repair(route_file_conn, damage):
    conn = route_file_conn
    if damage == "foreign_group":
        conn.execute("UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id='PROC-G'")
    elif damage == "cross_part_member":
        conn.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE part_no='PROC-003'")
    elif damage == "bad_range":
        conn.execute("UPDATE ExternalGroups SET start_seq=30 WHERE group_id='PROC-G'")
    elif damage == "bad_status":
        conn.execute("UPDATE PartOperations SET status=NULL WHERE part_no='PROC-001' AND seq=10")
    else:
        conn.execute("UPDATE PartOperations SET seq=0 WHERE part_no='PROC-001' AND seq=10")
    conn.commit()
    before = snapshot(conn)
    rows, _ = review(conn, decoded({"business_code": PART, "route_raw": ROUTE + "40new"}))
    assert rows[0]["result"] == "rejected"
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows)
    assert snapshot(conn) == before


def test_late_apply_failure_rolls_back_all_rows_refs_groups_confirmations_but_not_outer_work(route_file_conn):
    conn = route_file_conn
    conn.execute("""CREATE TRIGGER route_file_test_fail BEFORE INSERT ON PartOperations WHEN NEW.part_no='FAIL'
        BEGIN SELECT RAISE(ABORT,'injected late route failure'); END""")
    conn.commit()
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": "10车削30检验", "label": "rolled back"},
                                     {"business_code": "FAIL", "label": "also rolled back", "route_raw": "10车削"}))
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("UPDATE Batches SET quantity=23 WHERE batch_id='PROC-B'")
    before = snapshot(conn)
    with pytest.raises(sqlite3.IntegrityError, match="injected late route failure"):
        ProcessRouteFileOperations(conn).apply_rows(rows, discard_group_refs=[row["ref"] for row in extra["affected_groups"]],
                                                   confirm_zero_unit_hours=False)
    assert conn.in_transaction and snapshot(conn) == before
    conn.commit()
    assert conn.execute("SELECT quantity FROM Batches WHERE batch_id='PROC-B'").fetchone()[0] == 23


def test_confirmation_failure_after_persisting_route_is_still_atomic(route_file_conn, monkeypatch):
    conn = route_file_conn
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": "10车削30检验"}))
    before = snapshot(conn)

    def broken_confirmation(*args):
        assert "PROC-G" not in groups(conn)
        raise RuntimeError("injected workflow failure")

    monkeypatch.setattr("core.services.workbench.process_file_route.record_confirmation", broken_confirmation)
    with pytest.raises(RuntimeError, match="injected workflow failure"):
        apply(conn, rows, [row["ref"] for row in extra["affected_groups"]])
    assert snapshot(conn) == before


def test_success_releases_own_savepoint_without_committing_outer_transaction(route_file_conn):
    conn = route_file_conn
    before = snapshot(conn)
    rows, _ = review(conn, decoded({"business_code": "PENDING", "label": "pending"}))
    conn.execute("BEGIN IMMEDIATE")
    ProcessRouteFileOperations(conn).apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert conn.in_transaction and conn.execute("SELECT 1 FROM Parts WHERE part_no='PENDING'").fetchone()
    conn.rollback()
    assert snapshot(conn) == before


def test_apply_ref_guard_cannot_update_replacement_even_without_coordinator(route_file_conn):
    conn = route_file_conn
    rows, _ = review(conn, decoded({"business_code": "PROC-002", "label": "old target"}), ref(conn, code="PROC-002"))
    conn.execute("DELETE FROM Parts WHERE part_no='PROC-002'")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('PROC-002','replacement')")
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        apply(conn, rows)
    assert caught.value.code == "stale_write" and snapshot(conn) == before


def test_apply_guards_revision_and_preview_error_rows_even_without_coordinator(route_file_conn):
    conn = route_file_conn
    rows, _ = review(conn, decoded({"business_code": PART, "label": "preview"}))
    conn.execute("UPDATE Parts SET remark='concurrent change' WHERE part_no=?", (PART,))
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        apply(conn, rows)
    assert caught.value.code == "stale_write" and snapshot(conn) == before
    rows, _ = review(conn, decoded({"business_code": PART, "label": "preview"}))
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows * 2)
    assert snapshot(conn) == before


def test_write_lock_repreview_uses_same_full_canonical_document(route_file_conn):
    conn = route_file_conn
    source = decoded({"business_code": PART, "route_raw": ROUTE + "40new"}, {"business_code": "PENDING", "label": "new"})
    expected_rows, expected_extra = review(conn, source)
    with TransactionManager(conn).transaction(begin_immediate=True):
        current_rows, current_extra = review(conn, source)
        assert current_rows == expected_rows and current_extra == expected_extra
        result, refs = ProcessRouteFileOperations(conn).apply_rows(current_rows, discard_group_refs=[], confirm_zero_unit_hours=False)
        assert len(result) == len(refs) == 2
        # Facts ownership remains with the coordinator: read a fresh post-write service.
        assert len(WorkbenchProcessQueryService(conn).facts()["parts"]) == 6


@pytest.mark.parametrize("days", [None, 0, -2])
def test_new_external_operation_never_fills_missing_or_invalid_period_with_one_day(route_file_conn, days):
    conn = route_file_conn
    conn.execute("UPDATE Suppliers SET default_days=? WHERE supplier_id='PROC-S'", (days,))
    conn.commit()
    rows, _ = review(conn, decoded({"business_code": "NEW-EX", "label": "new external", "route_raw": "10热处理"}))
    assert rows[0]["route_summary"]["can_confirm_route"]
    apply(conn, rows)
    op = operations(conn, "NEW-EX")[10]
    assert op["source"] == "external" and op["supplier_id"] == "PROC-S" and op["ext_days"] is None
    assert op["setup_hours"] is None and op["unit_hours"] is None
    assert read_workflow(conn, "NEW-EX")["source"]["state"] == "unconfirmed"


def test_missing_history_ref_blocks_route_changes_without_allocating_replacement(route_file_conn):
    conn = route_file_conn
    old = operations(conn, "PROC-004")[10]
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref=?", (ref(conn, "template_operation", old["id"]),))
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        review(conn, decoded({"business_code": "PROC-004", "route_raw": "10车削20新序"}))
    assert caught.value.code == "storage_failure" and snapshot(conn) == before


def test_foreign_key_storage_contract_is_checked_before_any_apply(route_file_conn):
    conn = route_file_conn
    rows, _ = review(conn, decoded({"business_code": "NEW", "label": "pending"}))
    conn.execute("PRAGMA foreign_keys=OFF")
    before = snapshot(conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        apply(conn, rows)
    assert caught.value.code == "storage_failure" and snapshot(conn) == before
