"""Actual shipment counts distinguish known risk, zero and missing evidence."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard_external import external
from tests.workbench.dashboard_external_migration_support import external_v30_case as _external_v30_case  # noqa: F401
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import NOW, close_payload
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


@pytest.mark.parametrize("fixture,handling_supported", [("external_case", True), ("external_v30_case", False)])
def test_unregistered_operations_are_visible_unknown_not_zero(request, fixture, handling_supported):
    external_case = request.getfixturevalue(fixture)
    data, _ = external_case.read()
    summary = data["categories"]["external"]
    assert summary["state"] == "loaded" and summary["entry"]["enabled"] is True
    assert summary["kind"] == "outsourcing_receipts" and summary["tracking_basis"] == "manual_receipt_facts"
    assert summary["receipt_count"] == summary["assessed_count"] == summary["known_risk_count"] == 0
    assert summary["risk_count"] is None and summary["unknown_count"] == summary["unregistered_count"] == 3
    assert summary["source_gap_count"] == 0
    assert len(summary["evaluation_gaps"]) == 3
    assert {row["code"] for row in summary["evaluation_gaps"]} == {"outsourcing_unregistered"}
    assert {row["source_ref"] for row in summary["evaluation_gaps"]} == {
        external_case.shipments.operation_ref("XO" + str(index)) for index in range(1, 4)}
    assert summary["handling_supported"] is handling_supported and summary["handling_count"] == summary["closed_count"] == 0
    assert not any(row["category"] == "external" for row in data["items"])


@pytest.mark.parametrize("patch,expected", [
    ({"planned": "2026-09-11T12:00:00"}, (3, 0, 0, 0, 0)),
    ({"planned": NOW.isoformat(timespec="seconds")}, (3, 0, 0, 0, 0)),
    ({}, (3, 3, 0, 0, 3)),
    ({"confirmedState": "awaiting_confirmation", "planned": "2026-09-11T12:00:00"}, (3, 0, 0, 3, 3)),
    ({"confirmedState": "awaiting_confirmation"}, (3, 3, 0, 3, 3)),
    ({"confirmedState": "returned", "returned": "2026-09-10T10:00:00"}, (0, 0, 3, 0, 0)),
])
def test_fact_states_count_each_receipt_once(external_case, patch, expected):
    for index in range(1, 4):
        external_case.register(index, **patch)
    summary = external_case.read()[0]["categories"]["external"]
    keys = ("awaiting_return_count", "overdue_count", "returned_count", "awaiting_confirmation_count", "risk_count")
    assert tuple(summary[key] for key in keys) == expected
    assert summary["receipt_count"] == summary["current_receipt_count"] == summary["assessed_count"] == 3
    assert summary["unregistered_count"] == summary["unknown_count"] == summary["source_gap_count"] == 0
    assert summary["risk_count"] == summary["known_risk_count"]


def test_merged_receipt_counts_once_and_unregistered_member_stays_unknown(external_case):
    case = external_case
    ref = case.register(merged=True)
    summary = case.read()[0]["categories"]["external"]
    assert summary["receipt_count"] == summary["known_risk_count"] == summary["overdue_count"] == 1
    assert summary["risk_count"] is None and summary["unregistered_count"] == summary["unknown_count"] == 1
    assert len(case.shipments.detail(ref)["target"]["operation_refs"]) == 2


def test_no_formal_plan_does_not_hide_real_receipts(external_case):
    case = external_case
    case.register()
    before = case.read()[0]["categories"]["external"]
    case.conn.execute("DELETE FROM ScheduleHistory")
    case.conn.commit()
    data, _ = case.read()
    assert data["plan"] is None and data["categories"]["delivery"]["state"] == "no_official_plan"
    assert data["categories"]["external"] == before


def test_no_data_zero_only_after_complete_installed_read(external_case):
    case = external_case
    case.conn.execute("DELETE FROM BatchOperations WHERE source='external'")
    case.conn.commit()
    summary = case.read()[0]["categories"]["external"]
    assert summary["state"] == "no_data" and summary["entry"]["enabled"] is True
    assert summary["risk_count"] == summary["unknown_count"] == summary["receipt_count"] == 0


def test_return_reduces_risk_preserves_facts_and_existing_handling(external_case):
    case = external_case
    refs = [case.register(index) for index in range(1, 4)]
    item = case.item("delivery")
    case.command(item, close_payload())
    original_history = case.history(item["item_ref"])
    before = case.read()[0]["categories"]["external"]
    assert before["risk_count"] == 3
    for ref in refs:
        case.returned(ref)
    data, _ = case.read()
    assert data["categories"]["external"]["risk_count"] == 0
    assert data["categories"]["external"]["returned_count"] == 3
    assert case.history(item["item_ref"]) == original_history
    assert case.item("delivery")["risk"]["active"] is True
    assert case.item("delivery")["handling"]["status"] == "closed"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 6
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchProductionReports").fetchone()[0] == 0
    assert case.conn.execute("SELECT COUNT(*) FROM OperationExecutionEvents").fetchone()[0] == 0
    with case.shipments.reader.read_snapshot():
        history = case.shipments.reader.history(refs[0])
        assert history["history"]["page"]["total"] == 2
        assert history["history"]["items"][1]["after"]["returned"] is None


def test_default_lead_time_never_substitutes_for_actual_dates(external_case):
    case = external_case
    case.register(planned="2026-09-11T12:00:00")
    case.conn.execute("UPDATE Suppliers SET default_days=0")
    case.conn.execute("UPDATE BatchOperations SET ext_days=0 WHERE source='external'")
    case.conn.commit()
    summary = case.read()[0]["categories"]["external"]
    assert summary["known_risk_count"] == summary["overdue_count"] == 0
    assert summary["awaiting_return_count"] == 1 and summary["risk_count"] is None


def test_production_report_and_completed_flags_do_not_forge_receipts(external_case):
    case = external_case
    case.register()
    before = case.read()[0]["categories"]["external"]
    case.report()
    case.conn.execute("UPDATE BatchOperations SET status='completed' WHERE source='external'")
    case.conn.execute("UPDATE Batches SET status='completed' WHERE batch_id='XB1'")
    case.conn.commit()
    after = case.read()[0]["categories"]["external"]
    assert after == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchProductionReports").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 1


def test_external_read_requires_snapshot_and_original_ref_is_not_item(external_case):
    case = external_case
    with pytest.raises(RuntimeError, match="caller-owned snapshot"):
        external(case.conn, NOW)
    ref = case.register()
    from core.services.workbench.dashboard import WorkbenchDashboardService
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.detail(reader.read(NOW), ref)
    assert error.value.code == "entity_not_found"
