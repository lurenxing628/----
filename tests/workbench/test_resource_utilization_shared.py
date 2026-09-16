"""Same resource/time/source gives the same calendar occupancy everywhere."""

import csv
import io
import json
from datetime import datetime

import openpyxl
import pytest

from core.services.capacity.resource_utilization_metrics import METRIC_VERSION, ResourceUtilizationMetrics
from core.services.report.calculations import compute_utilization
from core.services.report.utilization_calendars import resource_calendars
from core.services.workbench.dashboard_resource_metrics import daily_resource_pressure
from tests.workbench.report_api_support import report_api as _report_api


def dt(value):
    return datetime.fromisoformat(value)


def resources(conn):
    conn.execute("INSERT INTO Machines(machine_id,name,status) VALUES ('M1','Machine','active')")
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('O1','Operator','active')")


def row(start, end, op=1):
    return dict(op_id=op, source="internal", machine_id="M1", operator_id="O1", start_time=start, end_time=end)


def shared(conn, rows, start, end):
    low, high = dt(start), dt(end)
    calendars = resource_calendars(conn, rows, low, high)
    machines, people = compute_utilization(schedule_rows=rows, start_dt=low, end_dt_excl=high, calendars=calendars)
    tasks = [dict(operation_ref=str(r["op_id"]), start=r["start_time"], end=r["end_time"]) for r in rows]
    for kind, report in (("machine", machines[0]), ("operator", people[0])):
        pressure = daily_resource_pressure(tasks, calendars[kind, "M1" if kind == "machine" else "O1"], start, end)
        assert pressure["window_metrics"] == {key: report[key] for key in pressure["window_metrics"]}
        assert report["metric_version"] == METRIC_VERSION
    return machines[0], people[0]


def test_overnight_weekend_personal_calendar_downtime_and_efficiency(schema_conn):
    resources(schema_conn)
    schema_conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_hours,efficiency) VALUES ('2026-09-04','workday','20:00',10,0.5)")
    schema_conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_hours,efficiency) VALUES ('O1','2026-09-04','workday','22:00',8,1.5)")
    schema_conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES ('M1','2026-09-05 01:00:00','2026-09-05 02:00:00','active')")
    tasks = [row("2026-09-04T20:00:00", "2026-09-07T10:00:00")]
    machine, person = shared(schema_conn, tasks, "2026-09-04T00:00:00", "2026-09-07T12:00:00")
    assert (machine["available_hours"], machine["occupied_hours"], machine["outside_calendar_hours"]) == (13, 11, 51)
    assert (person["available_hours"], person["occupied_hours"], person["outside_calendar_hours"]) == (12, 10, 52)
    assert machine["utilization"] == round(11 / 13, 6)
    assert person["utilization"] == round(10 / 12, 6)


def test_three_overlaps_are_excess_load_not_clamped_or_double_counted_outside(schema_conn):
    resources(schema_conn)
    tasks = [row("2026-09-07T07:00:00", "2026-09-07T17:00:00", op) for op in range(3)]
    machine, _ = shared(schema_conn, tasks, "2026-09-07T00:00:00", "2026-09-08T00:00:00")
    assert (machine["occupied_hours"], machine["summed_load_hours"], machine["overlap_hours"]) == (8, 24, 16)
    assert machine["outside_calendar_hours"] == 2
    assert machine["utilization"] == 1


@pytest.mark.parametrize("change,reason", [
    ("UPDATE Machines SET status='inactive'", "zero_available_capacity"),
    ("INSERT INTO WorkCalendar(date,day_type,shift_hours) VALUES ('2026-09-07','holiday',0)", "zero_available_capacity"),
    ("INSERT INTO WorkCalendar(date,day_type,shift_hours) VALUES ('2026-09-07','workday',-1)", "calendar_unavailable"),
])
def test_zero_and_unknown_capacity_remain_distinct(schema_conn, change, reason):
    resources(schema_conn)
    schema_conn.execute(change)
    machine, _ = shared(schema_conn, [row("2026-09-07T08:00:00", "2026-09-07T10:00:00")], "2026-09-07T00:00:00", "2026-09-08T00:00:00")
    assert machine["reason"] == reason and machine["utilization"] is None
    assert machine["occupied_hours"] == (0 if reason == "zero_available_capacity" else None)


def test_actual_intervals_do_not_fall_back_to_plan_and_boundaries_are_half_open():
    start, end = dt("2026-09-07T08:00:00"), dt("2026-09-07T16:00:00")
    metrics = ResourceUtilizationMetrics([], [(start, end)], source="actual").window(start, end)
    assert metrics["source"] == "actual" and metrics["occupied_hours"] == 0
    adjacent = ResourceUtilizationMetrics([(start, end)], [(start, end)]).window(end, dt("2026-09-08T00:00:00"))
    assert adjacent["occupied_hours"] == 0 and adjacent["available_hours"] == 0


@pytest.mark.parametrize("stream", [False, True])
def test_catalog_csv_xlsx_match_visible_metrics_and_snapshot(report_api, monkeypatch, stream):
    if stream:
        monkeypatch.setattr("core.services.report.report_engine.ReportEngine.EXPORT_DIRECT_MAX_ROWS", 0)
    path = "/api/workbench/v1/reports/utilization"
    query = dict(window_date_from="2026-09-02", window_date_to="2026-09-02", query="一号设备")
    response = report_api.client.get(path, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    data = payload["data"]
    metric = data["rows"][0]
    assert data["page"]["total"] == 1
    assert (metric["hours"], metric["capacity_hours"], metric["summed_load_hours"], metric["overlap_hours"], metric["outside_calendar_hours"]) == (.5, 7.5, 11.5, 11, 8.5)
    scope = dict(query, snapshot_ref=payload["meta"]["snapshot_ref"])
    csv_file = report_api.client.get(path + "/export", query_string=dict(scope, format="csv"))
    csv_row = list(csv.DictReader(io.StringIO(csv_file.data.decode("utf-8-sig"))))[0]
    for column in data["columns"]:
        if isinstance(metric[column["key"]], (float, int)):
            assert float(csv_row[column["label"]]) == metric[column["key"]]
    assert json.loads(csv_row["筛选范围"])["metric_version"] == METRIC_VERSION
    xlsx = report_api.client.get(path + "/export", query_string=dict(scope, format="xlsx"))
    assert xlsx.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx.data), read_only=True, data_only=True)
    try:
        values = list(workbook["设备负荷"].values)[1]
        assert values[2:10] == (metric["hours"], metric["task_count"], metric["capacity_hours"], metric["utilization_percent"], 11.5, 11, 8.5, METRIC_VERSION)
        assert json.loads(dict(workbook["查询摘要"].values)["筛选范围"])["plan_ref"] == data["plan"]["plan_ref"]
    finally:
        workbook.close()
    with report_api.db() as conn:
        conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='M1'")
    stale = report_api.client.get(path + "/export", query_string=dict(scope, format="csv"))
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
