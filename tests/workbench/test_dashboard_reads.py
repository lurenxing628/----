"""Real mixed-source reads and unknown/zero separation."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import DashboardQuery
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.dashboard_support import follow, source_rows


def test_current_official_mixed_risks_readonly(dashboard_case):
    case = dashboard_case
    before = source_rows(case.conn)
    changes = case.conn.total_changes
    case.conn.execute("PRAGMA query_only=ON")
    data, _ = case.read()
    assert data["plan"]["kind"] == "official" and data["plan"]["is_current_official"]
    assert {row["category"] for row in data["items"]} == {"delivery", "actual", "material", "downtime"}
    assert data["categories"]["external"]["risk_count"] == 0
    assert data["categories"]["external"]["state"] == "no_data"
    assert data["categories"]["external"]["entry"]["enabled"] is True
    assert data["categories"]["candidate"]["risk_count"] is None
    by_kind = {row["category"]: row for row in data["items"]}
    assert by_kind["delivery"]["source"]["evaluation"]["delay_hours"] == 10
    assert by_kind["material"]["source"]["requirements"][0]["available_quantity"] == 2
    assert by_kind["downtime"]["source"]["overlap_hours"] == 1
    assert by_kind["actual"]["risk"]["code"] == "feedback_pending"
    assert source_rows(case.conn) == before and changes == case.conn.total_changes


def test_latest_failed_not_replaced_by_old_official_or_candidate(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (2,'fixture','failed','{}')")
    case.conn.commit()
    data, _ = case.read()
    assert data["categories"]["delivery"]["state"] == "unavailable"
    assert data["categories"]["delivery"]["risk_count"] is None
    assert not any(row["category"] == "delivery" for row in data["items"])
    assert data["categories"]["material"]["known_risk_count"] == 1


def test_unknown_due_and_readiness_never_become_zero_or_alarm(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET due_date=?,ready_status=?", (b"bad-date", b"legacy-ready"))
    case.conn.execute("UPDATE BatchMaterials SET available_qty=?", (b"2",))
    case.conn.commit()
    before = source_rows(case.conn)
    data, _ = case.read()
    for kind in ("delivery", "material"):
        assert data["categories"][kind]["risk_count"] is None
        assert data["categories"][kind]["known_risk_count"] == 0
        assert len(data["categories"][kind]["evaluation_gaps"]) == 1
        assert len(data["categories"][kind]["evaluation_gaps"][0]["source_ref"]) == 48
        assert not any(row["category"] == kind for row in data["items"])
    assert source_rows(case.conn) == before


def test_known_zero_distinct_from_no_data_no_formal_and_not_read(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET due_date='2026-09-09',ready_status='yes'")
    case.conn.execute("UPDATE BatchMaterials SET available_qty=10,ready_status='yes'")
    case.conn.commit()
    data, _ = case.read()
    assert data["categories"]["delivery"]["risk_count"] == 0
    assert data["categories"]["material"]["risk_count"] == 0
    case.conn.execute("DELETE FROM ScheduleHistory")
    case.conn.commit()
    data, _ = case.read()
    assert data["categories"]["delivery"]["state"] == "no_official_plan"
    assert data["categories"]["delivery"]["risk_count"] is None
    case.conn.execute("DROP TABLE BatchMaterials")
    data, _ = case.read()
    assert data["categories"]["material"]["state"] == "unavailable"
    assert data["categories"]["material"]["risk_count"] is None


def test_full_report_uses_ledger_and_processing_hours_not_elapsed(dashboard_case):
    case = dashboard_case
    case.report()
    actual = case.item("actual")
    assert actual["source"]["completion_basis"] == "complete_reports"
    assert actual["source"]["hours"]["effective_processing_hours"] == 1.5
    assert actual["source"]["hours"]["quota_processing_hours"] == 1
    assert actual["source"]["risk_codes"] == ["finish_late", "processing_hours_overrun"]
    assert len(actual["source"]["report_refs"]) == 1
    assert actual["navigation"][0]["command_context"] == "read_execution_write_context"


def test_filter_before_page_counts_include_closed_live_risk(dashboard_case):
    case = dashboard_case
    case.command(case.item(), follow())
    data, _ = case.read(DashboardQuery(query="Planner", size=1))
    assert data["page"]["total"] == 1 and data["items"][0]["category"] == "delivery"
    with pytest.raises(WorkbenchCommandRejected):
        case.read(DashboardQuery(query="Planner", number=2, size=1))


def test_overlapping_downtime_is_unioned_and_cancelled_ignored(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time) VALUES ('DM1','2026-09-09T09:30:00','2026-09-09T12:00:00')")
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES ('DM1','2026-09-09T08:00:00','2026-09-09T10:00:00','cancelled')")
    case.conn.commit()
    item = case.item("downtime")
    assert item["source"]["overlap_hours"] == 1
    assert len(item["source"]["downtimes"]) == 2


def test_stored_completed_flag_does_not_erase_unready_facts(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET status='completed'")
    case.conn.commit()
    item = case.item("material")
    assert item["risk"]["active"] is True
    assert item["source"]["ready_status"] == "no"
    assert item["source"]["requirements"][0]["available_quantity"] == 2
