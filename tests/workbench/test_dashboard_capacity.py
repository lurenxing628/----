"""Bounded admission and verified shared resource/run summaries."""

import json
import time

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


def test_resource_pressure_comes_from_same_official_projection(dashboard_case):
    case = dashboard_case
    data, _ = case.read()
    pressure = data["resource_pressure"]
    assert pressure["plan_ref"] == data["plan"]["plan_ref"]
    assert pressure["basis"] == "selected_plan_only"
    machine = next(row for row in pressure["resources"] if row["kind"] == "machine")
    assert machine["occupied_hours"] == 2
    assert machine["utilization"] is None or 0 <= machine["utilization"] <= 1
    assert data["candidate_catalog"]["run_count"] == 0
    assert data["candidate_catalog"]["state"] == "no_data"
    assert data["categories"]["candidate"]["kind"] == "directory_not_risk"


def test_complete_source_limit_fails_instead_of_truncating(dashboard_case, monkeypatch):
    import core.services.workbench.dashboard_projection as projection

    case = dashboard_case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity) VALUES ('LIMIT','DP1','Part',1)")
    case.conn.commit()
    monkeypatch.setattr(projection, "MAX_ROWS", 1)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.read()
    assert error.value.code == "query_too_large"


def test_missing_item_identity_never_read_repairs(dashboard_case):
    case = dashboard_case
    case.conn.execute("DROP TRIGGER wb_dashboard_task_insert")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.read()
    assert error.value.code == "dashboard_unavailable"


def grow(case, count):
    case.conn.executemany("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
                          "VALUES (?,?,'DB1',?,'DT1','Turning','internal',0.5,0)",
                          ((index, "SCALE-" + str(index), index) for index in range(2, count + 1)))
    case.conn.executemany("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                          "VALUES (1,?,'DM1','DO1','2026-09-09T08:00:00','2026-09-09T10:00:00')", ((index,) for index in range(2, count + 1)))
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=?", (json.dumps({"scheduled_ops": count}),))
    case.conn.commit()


def test_2000_operation_real_sqlite_read_is_complete(dashboard_case, record_property):
    case = dashboard_case
    grow(case, 2000)
    started = time.perf_counter()
    data, _ = case.read()
    record_property("read_seconds_2000", round(time.perf_counter() - started, 4))
    assert data["categories"]["actual"]["known_risk_count"] == 2000
    assert data["categories"]["downtime"]["known_risk_count"] == 2000
    assert data["page"]["total"] == 4002
    assert len(data["items"]) == 100


def test_10001_plan_operations_rejected_before_public_truncation(dashboard_case):
    grow(dashboard_case, 10001)
    with pytest.raises(WorkbenchCommandRejected) as error:
        dashboard_case.read()
    assert error.value.code == "query_too_large"


def test_large_private_origin_rejected_before_write(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET remark=?", (b"x" * (8 * 1024 * 1024),))
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.read()
    assert error.value.code == "query_too_large"
