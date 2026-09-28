"""Resource defaults never replace facts in an existing confirmed process."""

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.process import workflow_state
from core.services.workbench.resource.entities import WorkbenchResourceService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import table_rows
from tests.workbench.process_workflow_support import confirm_all, workflow_database

_fixture = workflow_database


def set_policy(conn, mode):
    identity = WorkbenchIdentityRepository(conn).find_active("op_type", "TE")
    with TransactionManager(conn).transaction():
        WorkbenchResourceService(conn, "op_type").apply(
            "update", {"fields": {"default_merge_mode": mode}}, identity)


def confirmations(conn):
    return (table_rows(conn, "WorkbenchProcessWorkflow"),
            table_rows(conn, "WorkbenchProcessOperationConfirmations"))


def test_changing_resource_default_preserves_current_confirmation_and_group(workflow_conn):
    conn = workflow_conn
    expected = confirm_all(conn)
    records, groups = confirmations(conn), table_rows(conn, "ExternalGroups")
    operation_states = workflow_state.operation_confirmations(conn, "P1")
    for mode in ("merged", "separate", None):
        set_policy(conn, mode)
        changes = conn.total_changes
        assert workflow_state.read_workflow(conn, "P1") == expected
        assert workflow_state.operation_confirmations(conn, "P1") == operation_states
        workflow_state.require_template_ready(conn, "P1")
        assert confirmations(conn) == records
        assert table_rows(conn, "ExternalGroups") == groups
        assert conn.total_changes == changes


def test_broadening_work_type_to_both_preserves_chosen_source(workflow_conn):
    conn = workflow_conn
    expected = confirm_all(conn)
    previous = confirmations(conn)
    conn.execute("UPDATE OpTypes SET category='both'")
    conn.commit()
    assert workflow_state.read_workflow(conn, "P1") == expected
    assert confirmations(conn) == previous
    workflow_state.require_template_ready(conn, "P1")


@pytest.mark.parametrize("legacy_mode", (None, "merged", "separate"))
@pytest.mark.parametrize("change,stage", (
    ("UPDATE Suppliers SET status='inactive' WHERE supplier_id='S'", "source"),
    ("UPDATE Suppliers SET op_type_id=NULL WHERE supplier_id='S'", "source"),
    ("UPDATE ExternalGroups SET end_seq=4 WHERE group_id='P1-G'", "source"),
    ("UPDATE ExternalGroups SET merge_mode='merged',total_days=5 WHERE group_id='P1-G'", "source"),
    ("UPDATE PartOperations SET ext_days=4 WHERE part_no='P1' AND seq=3", "hours"),
))
def test_legacy_signatures_accept_only_default_changes_not_real_facts(workflow_conn, monkeypatch, legacy_mode, change, stage):
    conn = workflow_conn
    set_policy(conn, legacy_mode)
    current_facts = workflow_state._source_facts

    def legacy_facts(part, operation, group, suppliers):
        values, valid = current_facts(part, operation, group, suppliers)
        values[5] = operation["default_merge_mode"]
        return values, valid

    with monkeypatch.context() as patch:
        patch.setattr(workflow_state, "_source_facts", legacy_facts)
        expected = confirm_all(conn)
    records = confirmations(conn)
    for mode in ("merged", "separate", None):
        set_policy(conn, mode)
        changes = conn.total_changes
        assert workflow_state.read_workflow(conn, "P1") == expected
        assert confirmations(conn) == records
        assert conn.total_changes == changes
    conn.execute(change)
    conn.commit()
    assert workflow_state.read_workflow(conn, "P1")["stage"] == stage
    assert confirmations(conn) == records


@pytest.mark.parametrize("retained_days", (None, 0, -1, "bad", float("inf")))
def test_valid_merged_total_can_be_confirmed_with_unused_invalid_member_history(workflow_conn, retained_days):
    conn = workflow_conn
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=4 WHERE group_id='P1-G'")
    conn.execute("UPDATE PartOperations SET ext_days=? WHERE part_no='P1' AND seq=3", (retained_days,))
    conn.commit()
    expected = confirm_all(conn)
    conn.execute("UPDATE PartOperations SET ext_days=99 WHERE part_no='P1' AND seq=3")
    conn.commit()
    assert workflow_state.read_workflow(conn, "P1") == expected
    conn.execute("UPDATE ExternalGroups SET total_days=5 WHERE group_id='P1-G'")
    conn.commit()
    assert workflow_state.read_workflow(conn, "P1")["stage"] == "hours"


def test_legacy_merged_cycle_confirmation_is_verified_without_rewriting_it(workflow_conn, monkeypatch):
    conn = workflow_conn
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=4 WHERE group_id='P1-G'")
    conn.commit()
    current_facts = workflow_state._operation_facts

    def legacy_facts(part, operation, group, suppliers, records):
        route, signatures = current_facts(part, operation, group, suppliers, records)
        if group is not None and signatures["hours"] is not None:
            signatures["hours"] = workflow_state._digest([
                "hours-v1", signatures["source"], operation["setup_hours"], operation["unit_hours"],
                operation["ext_days"], group["total_days"]])
        return route, signatures

    with monkeypatch.context() as patch:
        patch.setattr(workflow_state, "_operation_facts", legacy_facts)
        expected = confirm_all(conn)
    records, changes = confirmations(conn), conn.total_changes
    assert workflow_state.read_workflow(conn, "P1") == expected
    assert confirmations(conn) == records and conn.total_changes == changes


def test_group_and_member_supplier_mismatch_cannot_be_confirmed(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,status,default_days) VALUES('OTHER','other','TE','active',3)")
    conn.execute("UPDATE PartOperations SET supplier_id='OTHER' WHERE part_no='P1' AND seq=3")
    conn.commit()
    assert workflow_state.read_workflow(conn, "P1")["stage"] == "source"
    with pytest.raises(ValidationError):
        with TransactionManager(conn).transaction():
            workflow_state.record_confirmation(conn, "P1", "source")
