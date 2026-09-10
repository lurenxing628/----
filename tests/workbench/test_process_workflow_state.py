"""Signatures are local, explicit, identity-bound and computed from current facts."""

from __future__ import annotations

import json
import re

import pytest

from core.infrastructure.errors import BusinessError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.process.part_service import PartService
from core.services.process.workflow_state import (
    operation_confirmations,
    read_workflow,
    record_confirmation,
    require_template_ready,
    start_workflow,
    workflow_snapshot,
)
from tests.workbench.identity_metadata_support import insert_row, table_rows
from tests.workbench.process_workflow_support import (
    business_rows,
    confirm_all,
    seed_large_workflow,
    seed_workflow,
    stored_state,
    workflow_database,
)


def test_legacy_get_never_infers_confirmations_even_for_source_and_zero_hours(workflow_conn):
    conn = workflow_conn
    before, changes = stored_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    view = read_workflow(conn, "P1")
    assert view["origin"] == "legacy" and not view["ready"] and view["route"]["state"] == "present"
    assert view["source"]["state"] == "unconfirmed" and view["hours"]["state"] == "locked"
    confirmations = operation_confirmations(conn, "P1")
    assert len(confirmations) == 3 and all(re.fullmatch("[0-9a-f]{48}", ref) for ref in confirmations)
    assert all(row == {stage: dict(state="unconfirmed", confirmed_at=None, confirmed_by=None)
                       for stage in ("source", "hours")} for row in confirmations.values())
    require_template_ready(conn, "P1")
    conn.execute("PRAGMA query_only=OFF")
    assert stored_state(conn) == before and conn.total_changes == changes


def test_order_explicit_zero_and_no_fabricated_person(workflow_conn):
    conn = workflow_conn
    before = business_rows(conn)
    for stage in ("source", "hours"):
        with pytest.raises(ValidationError):
            with TransactionManager(conn).transaction():
                record_confirmation(conn, "P1", stage)
    view = confirm_all(conn)
    assert view["origin"] == "managed" and view["stage"] == "ready"
    assert all(view[stage]["state"] == "confirmed" and view[stage]["confirmed_at"] and view[stage]["confirmed_by"] is None
               for stage in ("route", "source", "hours"))
    assert len(table_rows(conn, "WorkbenchProcessOperationConfirmations")) == 6
    assert business_rows(conn) == before
    require_template_ready(conn, "P1")


def test_transaction_required_and_owner_rollback(workflow_conn):
    conn = workflow_conn
    before = stored_state(conn)
    for fn, args in ((start_workflow, ()), (record_confirmation, ("route",))):
        with pytest.raises(RuntimeError, match="caller transaction"):
            fn(conn, "P1", *args)
    conn.execute("BEGIN")
    start_workflow(conn, "P1")
    record_confirmation(conn, "P1", "route")
    assert conn.in_transaction
    conn.rollback()
    assert stored_state(conn) == before


@pytest.mark.parametrize("person", ("", "  ", 5, False))
def test_invalid_person_does_not_write(workflow_conn, person):
    conn = workflow_conn
    before = stored_state(conn)
    with pytest.raises(ValidationError):
        with TransactionManager(conn).transaction():
            record_confirmation(conn, "P1", "route", person)
    assert stored_state(conn) == before


def test_identical_reconfirmation_preserves_all_times_and_people(workflow_conn):
    conn = workflow_conn
    confirm_all(conn, person="real operator")
    view, operations = read_workflow(conn, "P1"), operation_confirmations(conn, "P1")
    conn.execute("UPDATE Parts SET route_raw=route_raw")
    conn.execute("UPDATE PartOperations SET source=source,unit_hours=unit_hours")
    conn.execute("UPDATE OpTypes SET category=category")
    conn.commit()
    before, changes = stored_state(conn), conn.total_changes
    confirm_all(conn, person="another operator")
    assert read_workflow(conn, "P1") == view and operation_confirmations(conn, "P1") == operations
    assert stored_state(conn) == before and conn.total_changes == changes


def test_route_confirmation_allows_unknown_type_then_source_binds_it(workflow_conn):
    conn = workflow_conn
    conn.execute("UPDATE PartOperations SET op_type_id=NULL WHERE seq=1")
    conn.commit()
    with TransactionManager(conn).transaction():
        record_confirmation(conn, "P1", "route")
        with pytest.raises(ValidationError):
            record_confirmation(conn, "P1", "source")
        conn.execute("UPDATE PartOperations SET op_type_id='TI' WHERE seq=1")
        record_confirmation(conn, "P1", "source")
        assert record_confirmation(conn, "P1", "hours")["ready"]


def test_old_hours_service_invalidates_only_changed_operation(workflow_conn):
    from core.infrastructure.workbench_calibration_adoption_schema import install

    conn = workflow_conn
    with TransactionManager(conn).transaction():
        install(conn)
    confirm_all(conn)
    before = operation_confirmations(conn, "P1")
    PartService(conn).update_internal_hours("P1", 1, 0, 2.5)
    view, after = read_workflow(conn, "P1"), operation_confirmations(conn, "P1")
    assert view["stage"] == "hours" and view["source"]["state"] == "confirmed"
    changed = [ref for ref in before if before[ref] != after[ref]]
    assert len(changed) == 1 and after[changed[0]]["source"] == before[changed[0]]["source"]
    with pytest.raises(BusinessError):
        require_template_ready(conn, "P1")
    with TransactionManager(conn).transaction():
        record_confirmation(conn, "P1", "hours")
    final = operation_confirmations(conn, "P1")
    assert all(final[ref] == before[ref] for ref in before if ref not in changed)


@pytest.mark.parametrize("sql,stage", (
    ("UPDATE Parts SET route_raw='changed' WHERE part_no='P1'", "route"),
    ("UPDATE PartOperations SET seq=8 WHERE part_no='P1' AND seq=1", "route"),
    ("UPDATE PartOperations SET status='deleted' WHERE seq=1", "route"),
    ("UPDATE OpTypes SET category='external' WHERE op_type_id='TI'", "source"),
    ("UPDATE Suppliers SET status='inactive' WHERE supplier_id='S'", "source"),
    ("UPDATE Suppliers SET op_type_id='TI' WHERE supplier_id='S'", "source"),
    ("INSERT INTO WorkbenchSupplierProfiles VALUES('S','pending_review')", "source"),
    ("UPDATE ExternalGroups SET end_seq=4", "source"),
    ("UPDATE ExternalGroups SET merge_mode='merged',total_days=3", "source"),
    ("UPDATE PartOperations SET ext_days=3 WHERE seq=3", "hours"),
))
def test_relevant_legacy_fact_edits_invalidate_current_signatures(workflow_conn, sql, stage):
    conn = workflow_conn
    confirm_all(conn)
    conn.execute(sql)
    conn.commit()
    before, changes = stored_state(conn), conn.total_changes
    assert read_workflow(conn, "P1")["stage"] == stage
    with pytest.raises(BusinessError):
        require_template_ready(conn, "P1")
    assert stored_state(conn) == before and conn.total_changes == changes


def test_unrelated_rows_catalog_changes_and_capabilities_do_not_invalidate(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    before = read_workflow(conn, "P1")
    seed_workflow(conn, "P2", catalog=False)
    conn.execute("UPDATE PartOperations SET unit_hours=3 WHERE part_no='P2'")
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES('unrelated','other','external')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes VALUES('S','unrelated')")
    conn.execute("UPDATE OpTypes SET remark='unrelated' WHERE op_type_id='TI'")
    conn.execute("UPDATE Parts SET remark='unrelated',part_name='renamed' WHERE part_no='P1'")
    conn.commit()
    assert read_workflow(conn, "P1") == before


@pytest.mark.parametrize("table,key,value", (("PartOperations", "seq", 1), ("ExternalGroups", "group_id", "P1-G"),
                                             ("Suppliers", "supplier_id", "S"), ("OpTypes", "op_type_id", "TI")))
def test_delete_rebuild_same_business_key_never_inherits_confirmation(workflow_conn, table, key, value):
    conn = workflow_conn
    confirm_all(conn)
    conn.execute("PRAGMA foreign_keys=OFF")
    row = dict(conn.execute(f'SELECT * FROM "{table}" WHERE "{key}"=?', (value,)).fetchone())
    conn.execute(f'DELETE FROM "{table}" WHERE "{key}"=?', (value,))
    insert_row(conn, table, row)
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    assert not read_workflow(conn, "P1")["ready"]


def test_part_delete_rebuild_keeps_old_evidence_but_has_new_origin(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    old = table_rows(conn, "WorkbenchProcessWorkflow")
    conn.execute("DELETE FROM Parts WHERE part_no='P1'")
    conn.commit()
    seed_workflow(conn, catalog=False)
    assert read_workflow(conn, "P1")["origin"] == "legacy"
    assert table_rows(conn, "WorkbenchProcessWorkflow") == old
    assert all(row[stage]["state"] == "unconfirmed" for row in operation_confirmations(conn, "P1").values()
               for stage in ("source", "hours"))


@pytest.mark.parametrize("value", (None, -1, float("inf"), "bad"))
def test_invalid_hours_not_confirmable(workflow_conn, value):
    conn = workflow_conn
    with TransactionManager(conn).transaction():
        record_confirmation(conn, "P1", "route")
        record_confirmation(conn, "P1", "source")
        conn.execute("UPDATE PartOperations SET unit_hours=? WHERE seq=1", (value,))
        with pytest.raises(ValidationError):
            record_confirmation(conn, "P1", "hours")


def test_merged_group_uses_positive_total_not_inferred_operation_days(workflow_conn):
    conn = workflow_conn
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=4")
    conn.execute("UPDATE PartOperations SET ext_days=NULL WHERE seq=3")
    conn.commit()
    confirm_all(conn)
    conn.execute("UPDATE ExternalGroups SET total_days=5")
    conn.commit()
    assert read_workflow(conn, "P1")["stage"] == "hours"
    with TransactionManager(conn).transaction():
        record_confirmation(conn, "P1", "hours")
    conn.execute("UPDATE ExternalGroups SET total_days=NULL")
    conn.commit()
    assert read_workflow(conn, "P1")["stage"] == "hours"


def test_merged_group_retains_independent_positive_operation_days(workflow_conn):
    conn = workflow_conn
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=4")
    conn.commit()
    before = business_rows(conn)
    confirm_all(conn)
    assert business_rows(conn) == before
    assert conn.execute("SELECT ext_days FROM PartOperations WHERE seq=3").fetchone()[0] == 2.5


def test_removed_then_restored_operation_does_not_revive_confirmation(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    original = operation_confirmations(conn, "P1")
    removed_ref = conn.execute("""SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r
        ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT) WHERE o.seq=1""").fetchone()[0]
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE PartOperations SET status='deleted' WHERE seq=1")
        record_confirmation(conn, "P1", "route")
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE PartOperations SET status='active' WHERE seq=1")
        record_confirmation(conn, "P1", "route")
    current = operation_confirmations(conn, "P1")
    assert current[removed_ref]["source"]["state"] == "unconfirmed"
    assert current[removed_ref]["hours"]["state"] == "unconfirmed"
    assert all(current[ref] == row for ref, row in original.items() if ref != removed_ref)
    assert not read_workflow(conn, "P1")["ready"]


@pytest.mark.parametrize("table,column", (("WorkbenchProcessWorkflow", "hours_signature"),
                                         ("WorkbenchProcessOperationConfirmations", "signature")))
def test_well_formed_wrong_signatures_never_mean_ready(workflow_conn, table, column):
    conn = workflow_conn
    confirm_all(conn)
    conn.execute(f'UPDATE "{table}" SET "{column}"=?', ("0" * 64,))
    conn.commit()
    assert not read_workflow(conn, "P1")["ready"]


def test_workflow_snapshot_matches_single_reads_and_query_count_is_fixed(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)

    def measured_snapshot():
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            snapshot = workflow_snapshot(conn)
        finally:
            conn.set_trace_callback(None)
        return snapshot, sum(sql.lstrip().upper().startswith(("SELECT", "PRAGMA")) for sql in statements)

    first, first_count = measured_snapshot()
    for index in range(200):
        seed_workflow(conn, "PX" + str(index), catalog=False)
    before, changes = stored_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    many, many_count = measured_snapshot()
    assert many["P1"] == first["P1"] and len(many) == 201
    assert first_count == many_count and many_count <= 15
    assert json.loads(json.dumps(many, sort_keys=True, allow_nan=False)) == many
    for key in ("P1", "PX0", "PX199"):
        assert many[key] == {"workflow": read_workflow(conn, key), "operations": operation_confirmations(conn, key)}
    conn.execute("PRAGMA query_only=OFF")
    assert stored_state(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("external", (False, True))
def test_ten_thousand_operations_and_reconfirmation_are_bounded(workflow_conn, external, record_property):
    from time import perf_counter

    conn = workflow_conn
    seed_large_workflow(conn, external=external)
    confirm_all(conn)
    ticks = []
    conn.set_progress_handler(lambda: ticks.append(1) or int(len(ticks) > 20000), 1000)
    started = perf_counter()
    try:
        with TransactionManager(conn).transaction():
            assert record_confirmation(conn, "P1", "route")["ready"]
        snapshot = workflow_snapshot(conn)
    finally:
        conn.set_progress_handler(None, 0)
    assert len(snapshot["P1"]["operations"]) == 10000
    assert snapshot["P1"]["workflow"]["ready"]
    assert len(ticks) < 20000
    record_property("workflow_scale", {"external": external, "operations": 10000,
                                      "reconfirm_and_snapshot_seconds": perf_counter() - started,
                                      "sqlite_vm_steps_upper_bound": (len(ticks) + 1) * 1000})
