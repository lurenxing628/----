"""Actual auto assignment, overnight calendar, external lead time and fixed seeds."""

import pytest

from core.services.workbench.preflight import PreflightService
from tests.workbench.test_run_candidate_adoption_support import (
    INTENT,
    KEY,
    assert_retained,
    candidate,
    preview,
    service,
    snapshot,
)
from tests.workbench.test_run_candidate_adoption_support import candidate_case as _case  # noqa: F401


@pytest.mark.parametrize("mode", ["auto_assign", "multiday", "external", "locked"])
def test_real_resource_calendar_and_protected_seed_contracts(candidate_case, mode):
    case = candidate_case
    if mode == "auto_assign":
        case.conn.execute("UPDATE BatchOperations SET machine_id=NULL,operator_id=NULL")
    elif mode == "multiday":
        case.conn.execute("UPDATE BatchOperations SET unit_hours=5")
    elif mode == "external":
        case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
        case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL")
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                          "VALUES ('P1',1,'T1','Turning','external','S1',2)")
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
