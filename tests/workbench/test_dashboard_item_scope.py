"""Disposition guards bind complete item sources while page snapshots cover the catalog."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.execution.production_report import WorkbenchProductionReportService
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import NOW, follow
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


@pytest.mark.parametrize("category", ["delivery", "actual", "material", "downtime"])
def test_unrelated_batch_and_disposition_do_not_expire_an_item(dashboard_case, category):
    case = dashboard_case
    item = case.item(category)
    before = case.read()[1]["fingerprint"]
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) "
                      "VALUES ('OTHER','DP1','Other batch',1,'2026-09-08','no')")
    case.conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('UNUSED','Unused','kg',1)")
    case.conn.commit()
    other = next(row for row in case.read()[0]["items"]
                 if row["category"] == "material" and row["source"]["batch_id"] == "OTHER")
    case.command(other, follow())
    assert case.read()[1]["fingerprint"] != before
    saved = case.command(item, follow())
    assert saved["result"] == "committed" and saved["data"]["item_ref"] == item["item_ref"]


@pytest.mark.parametrize("category,sql,params", [
    ("delivery", "UPDATE Schedule SET lock_status='locked' WHERE version=1", ()),
    ("actual", "UPDATE BatchOperations SET setup_hours=? WHERE op_code='DOP1'", (1.5,)),
    ("downtime", "UPDATE MachineDowntimes SET reason_code='maintenance' WHERE machine_id='DM1'", ()),
    ("material", "INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) "
                 "SELECT id,'2026-10-01',1 FROM BatchMaterials WHERE batch_id='DB1'", ()),
])
def test_hidden_source_changes_stale_even_when_public_risk_is_equal(dashboard_case, category, sql, params):
    case = dashboard_case
    old = case.item(category)
    case.conn.execute(sql, params)
    case.conn.commit()
    current = case.item(category)
    assert current["source"] == old["source"] and current["risk"] == old["risk"]
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(old, follow())
    assert error.value.code == "stale_write"
    assert case.history(old["item_ref"]) == []


def test_other_operation_reporting_does_not_expire_actual_disposition(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) "
                      "VALUES ('DB2','DP1','Part',2,'2026-09-08','yes')")
    operation = case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
                                  "VALUES ('DOP2','DB2',1,'DT1','Turning','internal',0.5,0)").lastrowid
    case.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                      "VALUES (1,?,'DM1','DO1','2026-09-09T10:00:00','2026-09-09T12:00:00')", (operation,))
    case.conn.commit()
    actual = [row for row in case.read()[0]["items"] if row["category"] == "actual"]
    old = next(row for row in actual if row["source"]["batch_id"] == "DB1")
    other = next(row for row in actual if row["source"]["batch_id"] == "DB2")
    WorkbenchProductionReportService(case.conn, clock=lambda: NOW).execute(
        "create", other["source"]["task_ref"], {"completed_quantity": 1, "actual_start": "2026-09-09T10:00:00"},
        request_key="dashboard-unrelated-report-01", validate_context=lambda *_: None)
    assert case.command(old, follow())["result"] == "committed"


def test_official_plan_changes_do_not_expire_independent_external_disposition(external_handling_case):
    case = external_handling_case
    case.register()
    old = case.item("external")
    before = case.read()[1]["fingerprint"]
    case.plan(2)
    case.conn.commit()
    assert case.read()[1]["fingerprint"] != before
    assert case.command(old, follow())["result"] == "committed"
