"""Unknown birth and source replacements never inherit shipment facts."""

import pytest

from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_external_support import storage
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


@pytest.mark.parametrize("table,where", [("BatchOperations", "op_code='XO1'"),
                                       ("Batches", "batch_id='XB1'"), ("Suppliers", "supplier_id='XS1'")])
@pytest.mark.parametrize("returned", [False, True])
def test_same_number_replacement_does_not_inherit_risk_or_return(external_case, table, where, returned):
    case = external_case
    ref = case.register()
    if returned:
        case.returned(ref)
    old = case.shipments.detail(ref)
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + " WHERE " + where)
    case.conn.commit()
    before = storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    assert summary["state"] == "loaded" and summary["risk_count"] is None
    assert summary["receipt_count"] == 1 and summary["current_receipt_count"] == summary["known_risk_count"] == 0
    assert summary["returned_count"] == summary["overdue_count"] == 0
    assert summary["source_gap_count"] >= 1
    assert any(row["source_ref"] == ref for row in summary["evaluation_gaps"])
    current = case.shipments.detail(ref)
    assert current["source_state"] != "current"
    assert current["latest_fact_ref"] == old["latest_fact_ref"] and current["returned"] == old["returned"]
    assert storage(case.conn) == before
    if table == "BatchOperations":
        replacement = case.shipments.operation_ref("XO1")
        assert replacement != old["target"]["operation_refs"][0]
        assert any(row["source_ref"] == replacement and row["code"] == "outsourcing_unregistered"
                   for row in summary["evaluation_gaps"])


def test_operation_without_birth_mapping_stays_gap(external_case):
    case = external_case
    case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='XS1' WHERE op_code='DOP1'")
    case.conn.commit()
    ref = case.shipments.operation_ref("DOP1")
    # Seed a retained unknown origin, then restore the exact installed contract.
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_outsourcing_operationorigins_no_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_outsourcing_operationorigins_no_update")
    case.conn.execute("UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref=NULL WHERE operation_ref=?", (ref,))
    case.conn.execute(guard)
    case.conn.commit()
    assert case.conn.execute("SELECT batch_ref FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=?", (ref,)).fetchone()[0] is None
    before = storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    assert summary["risk_count"] is None and summary["unknown_count"] == summary["unregistered_count"] == 4
    assert summary["source_gap_count"] == 1
    assert next(row for row in summary["evaluation_gaps"] if row["source_ref"] == ref)["code"] == "identity_missing"
    assert storage(case.conn) == before


def test_missing_extension_is_not_connected_not_zero(dashboard_case):
    from core.infrastructure.workbench_outsourcing_schema import objects

    case = dashboard_case
    names = set(objects())
    installed = [(row[0], row[1]) for row in case.conn.execute("SELECT type,name FROM sqlite_master") if row[1] in names]
    for kind, name in installed:
        if kind != "table":
            case.conn.execute('DROP ' + kind.upper() + ' "' + name + '"')
    for name in ("WorkbenchOutsourcingFacts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingOperationOrigins"):
        case.conn.execute('DROP TABLE "' + name + '"')
    case.conn.commit()
    before = storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    assert summary["state"] == "not_connected" and summary["risk_count"] is None
    assert summary["entry"]["enabled"] is False and summary["receipt_count"] is None
    assert storage(case.conn) == before


@pytest.mark.parametrize("change", ["source", "semantics", "part"])
def test_registered_source_drift_is_gap_not_known_zero(external_case, change):
    case = external_case
    ref = case.register()
    if change == "source":
        case.conn.execute("UPDATE BatchOperations SET source='internal' WHERE op_code='XO1'")
    elif change == "semantics":
        case.conn.execute("UPDATE BatchOperations SET op_type_name='Different process' WHERE op_code='XO1'")
    else:
        case.conn.execute("UPDATE Batches SET part_no='DP1' WHERE batch_id='XB1'")
    case.conn.commit()
    summary = case.read()[0]["categories"]["external"]
    assert summary["current_receipt_count"] == summary["known_risk_count"] == 0 and summary["risk_count"] is None
    assert summary["unknown_count"] == 3 and summary["source_gap_count"] == 1
    assert len([row for row in summary["evaluation_gaps"] if row["source_ref"] == ref]) == 1


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("source", [None, b"external", "unknown"])
def test_unknown_source_is_visible_without_double_count(external_case, registered, source):
    case = external_case
    ref = case.register() if registered else case.shipments.operation_ref("XO1")
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE op_code='XO1'", (source,))
    case.conn.commit()
    before = storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    assert summary["unknown_count"] == 3 and summary["source_gap_count"] == 1
    assert summary["risk_count"] is None and summary["known_risk_count"] == 0
    gaps = [row for row in summary["evaluation_gaps"] if row["source_ref"] == ref]
    assert len(gaps) == 1
    assert gaps[0]["code"] == ("constraint_conflict" if registered else "external_source_unknown")
    assert storage(case.conn) == before


def test_partial_schema_is_unavailable_not_not_connected(external_case):
    case = external_case
    case.register()
    case.conn.execute("DROP TRIGGER wb_outsourcing_facts_no_update")
    case.conn.commit()
    before = storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    assert summary["state"] == "unavailable" and summary["risk_count"] is None
    assert summary["receipt_count"] is None and summary["entry"]["enabled"] is False
    assert summary["issues"][0]["code"] == "outsourcing_unavailable"
    assert storage(case.conn) == before


@pytest.mark.parametrize("column,value", [("planned", "invalid-date"), ("sent", b"invalid-time"),
                                         ("confirmed_state", "unknown")])
def test_invalid_stored_facts_are_gaps_without_false_risk(external_case, column, value):
    case = external_case
    ref = case.register()
    # Simulate legacy invalid storage, restoring all guards before the read.
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_outsourcing_facts_no_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_outsourcing_facts_no_update")
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.conn.execute("UPDATE WorkbenchOutsourcingFacts SET " + column + "=? WHERE outsourcing_ref=?", (value, ref))
    case.conn.execute(guard)
    case.conn.commit()
    case.conn.execute("PRAGMA ignore_check_constraints=OFF")
    before = storage(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    summary = case.read()[0]["categories"]["external"]
    assert summary["receipt_count"] == 1 and summary["current_receipt_count"] == summary["known_risk_count"] == 0
    assert summary["risk_count"] is None and summary["source_gap_count"] == 1
    assert next(row for row in summary["evaluation_gaps"] if row["source_ref"] == ref)["code"] == "outsourcing_fact_invalid"
    assert storage(case.conn) == before
