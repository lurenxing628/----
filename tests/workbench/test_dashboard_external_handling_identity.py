"""Permanent receipt/member identities; unknown never creates a disposition."""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_handling_support import external_items, production_storage
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import close_payload, follow
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


@pytest.mark.parametrize("table,where", [("BatchOperations", "op_code='XO1'"), ("Batches", "batch_id='XB1'"), ("Suppliers", "supplier_id='XS1'")])
def test_source_replacement_does_not_inherit_old_disposition(external_handling_case, table, where):
    case = external_handling_case
    ref = case.register()
    original = case.item("external")
    case.command(original, close_payload())
    stale = case.item("external")
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + " WHERE " + where)
    case.conn.commit()
    before = production_storage(case.conn)
    old = case.item("external")
    assert old["item_ref"] == original["item_ref"] and old["source"]["outsourcing_ref"] == ref
    assert old["risk"]["active"] is None and old["source_state"] == "not_currently_evaluated"
    assert old["handling"]["status"] == "closed" and not old["navigation"][0]["enabled"]
    assert old["source"]["operation_refs"] == original["source"]["operation_refs"]
    assert production_storage(case.conn) == before
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(stale, {"reason": "Recheck"}, action="reopen")
    assert error.value.code == "stale_write"
    if table == "BatchOperations":
        replacement = case.register()
        current = next(row for row in external_items(case) if row["source"]["outsourcing_ref"] == replacement)
        assert current["item_ref"] != old["item_ref"] and current["handling"]["status"] == "new"
        assert current["handling"]["history_count"] == 0
        assert current["source"]["operation_refs"] != old["source"]["operation_refs"]


@pytest.mark.parametrize("saved", [False, True])
def test_invalid_fact_stays_unknown_without_guessing_or_mutating(external_handling_case, saved):
    case = external_handling_case
    ref = case.register()
    if saved:
        case.command(case.item("external"), follow())
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_outsourcing_facts_no_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_outsourcing_facts_no_update")
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.conn.execute("UPDATE WorkbenchOutsourcingFacts SET sent=? WHERE outsourcing_ref=?", (b"unknown-time", ref))
    case.conn.execute(guard)
    case.conn.commit()
    case.conn.execute("PRAGMA ignore_check_constraints=OFF")
    case.conn.execute("PRAGMA query_only=ON")
    before = production_storage(case.conn)
    items = external_items(case)
    assert len(items) == int(saved)
    if saved:
        assert items[0]["risk"]["active"] is None and items[0]["handling"]["status"] == "following"
    summary = case.read()[0]["categories"]["external"]
    assert summary["risk_count"] is None and summary["known_risk_count"] == 0
    assert summary["source_gap_count"] == 1
    assert production_storage(case.conn) == before


def test_merged_members_are_not_inferred_from_template_or_plan(external_handling_case):
    case = external_handling_case
    ref = case.register(merged=True)
    item = case.item("external")
    expected = sorted([case.shipments.operation_ref("XO1"), case.shipments.operation_ref("XO2")])
    assert item["source"]["operation_refs"] == expected and item["source"]["outsourcing_ref"] == ref
    case.command(item, follow())
    case.conn.execute("UPDATE BatchOperations SET ext_days=99 WHERE source='external'")
    case.conn.execute("DELETE FROM ScheduleHistory")
    case.conn.commit()
    current = case.item("external")
    assert current["item_ref"] == item["item_ref"] and current["source"]["operation_refs"] == expected
    assert current["source"]["receipt"]["returned"] is None and current["risk"]["active"] is True
    assert len(external_items(case)) == 1


def test_raw_source_evidence_is_preserved_and_type_drift_rejects_old_write(external_handling_case):
    case = external_handling_case
    case.register()
    case.conn.execute("UPDATE Suppliers SET remark=? WHERE supplier_id='XS1'", (b"same-text",))
    case.conn.commit()
    before = production_storage(case.conn)
    case.command(case.item("external"), follow())
    history = json.loads(case.conn.execute("SELECT source_facts_json FROM WorkbenchDashboardExternalHistory").fetchone()[0])
    assert history["facts"]["snapshot"]["source"]["facts"]["supplier"]["row"]["remark"] == {
        "storage_type": "blob", "hex": b"same-text".hex()}
    assert production_storage(case.conn) == before
    old = case.item("external")
    case.conn.execute("UPDATE Suppliers SET remark='same-text' WHERE supplier_id='XS1'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(old, follow(remark="Rechecked dispatch"))
    assert error.value.code == "stale_write"
