"""Atomic writes, retained legacy facts and non-authoritative confirmation results."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import operation_confirmations, read_workflow
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from tests.workbench.test_process_file_hours_support import (
    apply,
    confirmations,
    groups,
    hours_database,
    op_rows,
    part_ref,
    preview,
    reconfirm_source,
    snapshot,
)


def test_sparse_updates_preserve_all_hidden_orphan_downstream_and_confirmation_facts(hours_conn, monkeypatch):
    before = snapshot(hours_conn)
    operations, original_groups, stamps = op_rows(hours_conn), groups(hours_conn), confirmations(hours_conn)
    states = operation_confirmations(hours_conn, "P1")

    def forbidden(*args, **kwargs):
        pytest.fail("File imports must never record a stage confirmation")

    monkeypatch.setattr("core.services.process.workflow_state.record_confirmation", forbidden)
    rows, extra = preview(hours_conn, {"sequence": 1, "unit_hours": 2.125, "external_days": None},
                          {"sequence": 3, "external_days": None, "setup_hours": None, "unit_hours": None,
                           "group_total_days": 9.25}, {"sequence": 5, "group_total_days": 9.25})
    results, refs = apply(hours_conn, rows)
    assert len(results) == 3 and all(row["result"] == "committed" for row in results)
    assert refs == [part_ref(hours_conn)] and extra["affected_groups"] == []
    assert all(set(row) == {"row", "result", "entity_ref", "business_code", "sequence"} for row in results)
    assert op_rows(hours_conn) == {**operations, 1: {**operations[1], "unit_hours": 2.125},
                                  3: {**operations[3], "ext_days": None}}
    assert groups(hours_conn) == {**original_groups, "P1-G": {**original_groups["P1-G"], "total_days": 9.25}}
    after = snapshot(hours_conn)
    assert before[0] == after[0]
    for table in before[1]:
        if table not in ("PartOperations", "ExternalGroups", "WorkbenchEntityRefs"):
            assert before[1][table] == after[1][table], table
    assert confirmations(hours_conn) == stamps
    workflow = read_workflow(hours_conn, "P1")
    assert workflow["source"]["state"] == "confirmed" and workflow["hours"]["state"] == "unconfirmed"
    current = operation_confirmations(hours_conn, "P1")
    selected = {row["expected"]["operation_ref"] for row in rows}
    for ref, old in states.items():
        assert current[ref]["source"] == old["source"]
        assert current[ref]["hours"] == (old["hours"] if ref not in selected else
                                       {"state": "unconfirmed", "confirmed_at": None, "confirmed_by": None})
    old_refs = {row[0]: row for row in before[1]["WorkbenchEntityRefs"]}
    changed_refs = {row["expected"]["operation_ref"] for row in rows[:2]} | {rows[1]["expected"]["group"]["ref"]}
    columns = [row[1] for row in hours_conn.execute("PRAGMA table_info(WorkbenchEntityRefs)")]
    for row in after[1]["WorkbenchEntityRefs"]:
        old, new = dict(zip(columns, old_refs[row[0]])), dict(zip(columns, row))
        assert new == {**old, "revision": old["revision"] + (row[0] in changed_refs)}


def test_group_only_edit_invalidates_all_members_without_updating_their_rows(hours_conn):
    operations, stamps = op_rows(hours_conn), confirmations(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "group_total_days": 7.25})
    apply(hours_conn, rows)
    assert op_rows(hours_conn) == operations and confirmations(hours_conn) == stamps
    states = operation_confirmations(hours_conn, "P1")
    assert sum(row["hours"]["state"] == "unconfirmed" for row in states.values()) == 2
    assert all(row["source"]["state"] == "confirmed" for row in states.values())


def test_unchanged_preserves_original_confirmation_times_and_does_no_update(hours_conn):
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 0.0},
                      {"sequence": 3, "external_days": 2.5, "group_total_days": 6.75})
    statements = []
    hours_conn.set_trace_callback(statements.append)
    try:
        results, _ = apply(hours_conn, rows, ack=True)
    finally:
        hours_conn.set_trace_callback(None)
    assert [row["result"] for row in results] == ["unchanged", "unchanged"]
    assert snapshot(hours_conn) == before
    assert not any(sql.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")) for sql in statements)


def test_repeated_import_is_unchanged_but_does_not_reconfirm_stale_hours(hours_conn):
    stamps = confirmations(hours_conn)
    values = {"sequence": 1, "unit_hours": 2.125}
    rows, _ = preview(hours_conn, values)
    assert apply(hours_conn, rows)[0][0]["result"] == "committed"
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, values)
    assert apply(hours_conn, rows)[0][0]["result"] == "unchanged"
    assert snapshot(hours_conn) == before and confirmations(hours_conn) == stamps
    assert read_workflow(hours_conn, "P1")["hours"]["state"] == "unconfirmed"


def test_partial_file_does_not_default_or_validate_unprovided_missing_hours(hours_conn):
    hours_conn.execute("UPDATE PartOperations SET setup_hours=NULL,unit_hours=NULL WHERE part_no='P1' AND seq=1")
    hours_conn.commit()
    rows, extra = preview(hours_conn, {"sequence": 1, "unit_hours": 0})
    assert rows[0]["before"]["setup_hours"] is None and rows[0]["after"]["setup_hours"] is None
    assert extra["zero_review_required"] and rows[0]["warnings"][0]["code"] == "zero_unit_hours_review"
    before = snapshot(hours_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        apply(hours_conn, rows)
    assert exc.value.code == "zero_unit_hours_review" and snapshot(hours_conn) == before
    apply(hours_conn, rows, ack=True)
    assert op_rows(hours_conn)[1]["setup_hours"] is None and op_rows(hours_conn)[1]["unit_hours"] == 0
    assert not read_workflow(hours_conn, "P1")["ready"]


@pytest.mark.parametrize("ack", (None, 0, 1, "true", []))
def test_zero_ack_must_be_an_explicit_boolean(hours_conn, ack):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 0})
    before = snapshot(hours_conn)
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, rows, ack=ack)
    assert snapshot(hours_conn) == before


def test_group_discard_is_never_supported_and_transaction_is_required(hours_conn):
    rows, _ = preview(hours_conn, {"sequence": 3, "group_total_days": 7.25})
    service = ProcessHoursFileOperations(hours_conn)
    with pytest.raises(RuntimeError, match="外层"):
        service.apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=False)
    before = snapshot(hours_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        apply(hours_conn, rows, discard=[rows[0]["expected"]["group"]["ref"]])
    assert exc.value.code == "group_discard_mismatch" and snapshot(hours_conn) == before


@pytest.mark.parametrize("fail_group", (False, True))
def test_savepoint_rolls_back_partial_writes_even_when_outer_catches_error(hours_conn, fail_group):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2},
                      {"sequence": 3, "external_days": 3, "group_total_days": 7.25})
    table = "ExternalGroups" if fail_group else "PartOperations"
    condition = "NEW.group_id='P1-G'" if fail_group else "NEW.part_no='P1' AND NEW.seq=3"
    hours_conn.execute("CREATE TEMP TRIGGER hours_file_abort BEFORE UPDATE ON " + table + " WHEN " + condition
                       + " BEGIN SELECT RAISE(ABORT, 'injected write failure'); END")
    service = ProcessHoursFileOperations(hours_conn)
    with TransactionManager(hours_conn).transaction(begin_immediate=True):
        hours_conn.execute("UPDATE Parts SET remark='outer kept' WHERE part_no='P2'")
        before = snapshot(hours_conn)
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            service.apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=False)
        assert hours_conn.in_transaction and snapshot(hours_conn) == before
    assert hours_conn.execute("SELECT remark FROM Parts WHERE part_no='P2'").fetchone()[0] == "outer kept"


def test_outer_failure_rolls_back_successful_provisional_results(hours_conn):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2}, {"sequence": 3, "group_total_days": 8.5})
    before = snapshot(hours_conn)
    with pytest.raises(RuntimeError, match="receipt failed"):
        with TransactionManager(hours_conn).transaction(begin_immediate=True):
            result, _ = ProcessHoursFileOperations(hours_conn).apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=False)
            assert all(row["result"] == "committed" for row in result) and hours_conn.in_transaction
            raise RuntimeError("receipt failed")
    assert snapshot(hours_conn) == before


@pytest.mark.parametrize("group_change", (False, True))
def test_identity_revision_guard_rolls_back_already_updated_rows(hours_conn, group_change):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2}, {"sequence": 3, "external_days": 3, "group_total_days": 8.5})
    sql = ("UPDATE ExternalGroups SET remark='newer' WHERE group_id='P1-G'" if group_change else
           "UPDATE PartOperations SET unit_hours=99 WHERE part_no='P1' AND seq=3")
    hours_conn.execute(sql)
    hours_conn.commit()
    before = snapshot(hours_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        apply(hours_conn, rows)
    assert exc.value.code == "stale_write" and snapshot(hours_conn) == before


def test_conflicting_same_group_rejects_every_member_before_any_write(hours_conn):
    rows, _ = preview(hours_conn, {"sequence": 3, "group_total_days": 7}, {"sequence": 5, "group_total_days": 8})
    assert all(row["result"] == "rejected" and any(error["code"] == "group_value_conflict" for error in row["errors"]) for row in rows)
    before = snapshot(hours_conn)
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, rows)
    assert snapshot(hours_conn) == before


def test_group_value_is_written_once_and_all_row_previews_show_effect(hours_conn, monkeypatch):
    rows, _ = preview(hours_conn, {"sequence": 3, "group_total_days": 8}, {"sequence": 5, "external_days": 4.25})
    assert all(row["after"]["group_total_days"] == 8 and row["result"] == "update" for row in rows)
    service, calls = ProcessHoursFileOperations(hours_conn), []
    original = service._update

    def recording(*args):
        calls.append(args[0])
        original(*args)

    monkeypatch.setattr(service, "_update", recording)
    with TransactionManager(hours_conn).transaction(begin_immediate=True):
        service.apply_rows(rows, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert calls == ["ExternalGroups"]


def test_multi_part_results_return_unique_real_partrefs_not_operation_refs(hours_conn):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2}, {"sequence": 3, "external_days": 3},
                      {"business_code": "P2", "sequence": 1, "unit_hours": 2})
    results, refs = apply(hours_conn, rows)
    assert refs == sorted([part_ref(hours_conn), part_ref(hours_conn, "P2")])
    assert set(refs) == {row["entity_ref"] for row in results}
    assert [row["entity_ref"] for row in rows] == [part_ref(hours_conn), part_ref(hours_conn), part_ref(hours_conn, "P2")]
    assert not set(refs) & {row["expected"]["operation_ref"] for row in rows}


def test_separate_group_hidden_total_survives_null_export_columns(hours_conn):
    hours_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='P1-G'")
    hours_conn.commit()
    reconfirm_source(hours_conn)
    old = groups(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": 8.5, "group_total_days": None})
    apply(hours_conn, rows)
    assert groups(hours_conn) == old and op_rows(hours_conn)[3]["ext_days"] == 8.5
