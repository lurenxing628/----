"""Actual auto assignment, overnight calendar, external lead time and fixed seeds."""

import json
from datetime import datetime

import pytest

from core.services.workbench.resource.downtimes import WorkbenchDowntimeService
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import (
    INTENT,
    KEY,
    assert_retained,
    candidate,
    preview,
    service,
    snapshot,
)
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401


@pytest.mark.parametrize("mode", ["auto_assign", "multiday", "external", "locked"])
def test_real_resource_calendar_and_protected_seed_contracts(candidate_case, mode):
    case = candidate_case
    if mode == "auto_assign":
        case.conn.execute("UPDATE BatchOperations SET machine_id=NULL,operator_id=NULL")
    elif mode == "multiday":
        case.conn.execute("UPDATE BatchOperations SET unit_hours=5")
    elif mode == "external":
        case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
        case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                          "VALUES ('P1',1,'T1','Turning','external','S1',2)")
        case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL")
    elif mode == "locked":
        case.operation(seq=2)
        case.plan(1, [case.op_id], end="2026-09-09T08:45:00")
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    version = result["data"]["official_plan"]["version"]
    row = case.conn.execute("SELECT * FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone()
    if mode == "external":
        assert row["machine_id"] is None and row["operator_id"] is None
    elif mode == "auto_assign":
        assert (row["machine_id"], row["operator_id"]) == ("M1", "O1")
        assert case.conn.execute("SELECT machine_id FROM BatchOperations WHERE id=?", (case.op_id,)).fetchone()[0] is None
    elif mode == "locked":
        assert row["lock_status"] == "locked" and row["start_time"] == "2026-09-09 08:00:00"
    assert_retained(before, snapshot(case.conn))


def test_started_work_needing_reconciliation_is_not_admitted_by_upstream(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    before = snapshot(case.conn)
    data, _ = PreflightService(case.conn).evaluate(case.settings())
    assert "execution_review_required" in {item["code"] for item in data["blockers"]}
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("unit,efficiency", [(0.001, 1.0), (0.25, 0.95)])
def test_piece_real_computation_and_adoption_preserve_fractional_seconds(candidate_case, unit, efficiency):
    case = candidate_case
    split(case, common=False, unit=unit, quantity=1)
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,shift_start,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('2026-09-09','workday',8,'08:00',?,'yes','yes')", (efficiency,))
    case.conn.commit()
    ref = candidate(case)
    expected = {row["op_id"]: (datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"]))
                for row in (json.loads(item[0]) for item in case.conn.execute(
                    "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,)))}
    assert any(end.microsecond for _, end in expected.values())
    result = service(case.conn).adopt(ref, preview(case, ref), KEY, INTENT)
    stored = {row[0]: (datetime.fromisoformat(row[1]), datetime.fromisoformat(row[2]))
              for row in case.conn.execute("SELECT op_id,start_time,end_time FROM Schedule WHERE version=?",
                                           (result["data"]["official_plan"]["version"],))}
    assert stored == expected


@pytest.mark.parametrize("run_start", ["2026-09-09", "2026-09-10"])
def test_window_boundary_cannot_hide_downtime_of_legitimately_locked_work(candidate_case, run_start):
    case = candidate_case

    def run(number, settings=None):
        accepted = case.accept(key="locked-calendar-run-" + str(number).zfill(5), settings=settings)
        computed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        return computed["candidates"][0]["candidate_ref"]

    def adopt(number, ref):
        return service(case.conn).adopt(ref, preview(case, ref), "locked-calendar-adopt-" + str(number).zfill(5), INTENT)

    adopt(1, run(1))
    case.operation(seq=2)
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    adopt(2, run(2))
    case.config(freeze_window_enabled="no")
    assert case.conn.execute("SELECT lock_status FROM Schedule WHERE version=2 AND op_id=?", (case.op_id,)).fetchone()[0] == "locked"
    downtime = WorkbenchDowntimeService(case.conn)
    machine_ref = case.ref("machine", "M1")
    state = downtime.snapshot(machine_ref)
    case.conn.execute("BEGIN IMMEDIATE")
    downtime.apply(machine_ref, "create", {"start_time": "2026-09-09 08:00", "end_time": "2026-09-09 09:00",
                                            "reason_code": "maintenance", "reason_detail": None}, state)
    case.conn.commit()
    assert case.conn.execute("SELECT count(*) FROM OperationExecutionEvents").fetchone()[0] == 0
    assert case.conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts").fetchone()[0] == 0
    ref = run(3, case.settings(start_date=run_start))
    before = snapshot(case.conn)
    checked = service(case.conn).preview(ref)
    assert checked["validation"]["can_adopt"] is False
    assert checked["validation"]["issues"][0]["code"] == "candidate_calendar_duration_conflict"
    assert snapshot(case.conn) == before
