"""One dashboard capture supplies its projections and calendar source reads."""

import sqlite3
from collections import Counter
from datetime import date, datetime

import pytest

from core.infrastructure.sqlite_udf import SQL_PARSE_FUNCTION, parse_dt_for_sql, register_schedule_time_sql_functions
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_io import CalendarFacts, CapturedCalendarInputs, ProjectionLimit
from core.services.capacity.plan_calendar_windows import project_resource_calendars
from core.services.workbench.dashboard import downtime, execution
from core.services.workbench.dashboard import facts as facts_module
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.dashboard.analysis_projection import project_dashboard_analysis
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.calendar_facts_repo import _DOWNTIMES_SQL, CalendarFactsRepository
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository


@pytest.fixture
def dashboard_case(tmp_path):
    from tests.workbench.dashboard_support import dashboard_case as existing_case
    yield from existing_case.__wrapped__(tmp_path)


def test_one_capture_reuses_projections_and_only_reads_new_identity_keys(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import NOW
    case, calls, keys, sql = dashboard_case, Counter(), [], []
    for name, module in (("actual", execution), ("downtime", downtime)):
        original = getattr(module, name)

        def tracked(*args, _name=name, _original=original):
            calls[_name] += 1
            return _original(*args)

        monkeypatch.setattr(module, name, tracked)
    original_refs = DashboardSourceRepository.entity_ref_rows

    def refs(repo, kind, requested):
        keys.append((kind, list(requested)))
        return original_refs(repo, kind, requested)

    monkeypatch.setattr(DashboardSourceRepository, "entity_ref_rows", refs)
    enriched, enrich = [], WorkbenchPlanCatalogRepository.enrich_arrangements

    def enrich_once(repo, arrangements, *, captured_machines=None):
        enriched.append(captured_machines)
        return enrich(repo, arrangements, captured_machines=captured_machines)

    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "enrich_arrangements", enrich_once)
    case.conn.set_trace_callback(sql.append)
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
        facts, material = sources.facts, sources.material
        assert facts.plan_state == "loaded" and len(facts.tasks) == 1
        assert facts.entity_refs("batch", ["DB1"]) is not facts.entity_refs("batch", ["DB1"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["DB1", "missing-batch"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["missing-batch"])
    monkeypatch.setattr(facts_module, "candidate_catalog", lambda _: pytest.fail("Analysis read candidate catalog"))
    data = reader.project(sources)
    assert len(enriched) == 1 and enriched[0] is facts.raw["Machines"]
    assert sorted(item["category"] for item in data["items"]) == ["actual", "delivery", "downtime", "material"]
    assert data["categories"]["external"]["state"] == "no_data"
    assert [requested for kind, requested in keys if kind == "batch"] == [["DB1"], ["missing-batch"]]
    rows, _ = facts.observations("actual")
    assert facts.observations("actual")[0] is rows
    facts.observations("downtime")
    projected = project_dashboard_analysis(facts, material, query=DashboardAnalysisQuery("actual"))
    assert len(projected["tasks"]) == 1 and calls == {"actual": 1, "downtime": 1}
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum(" FROM SQLITE_MASTER" in statement for statement in normalized) == 0
    assert sum("FROM MACHINEDOWNTIMES " in statement for statement in normalized) == 1
    assert sum("FROM MACHINES " in statement for statement in normalized) == 1
    assert sum("FROM SCHEMAVERSION " in statement for statement in normalized) == 1


@pytest.mark.parametrize("captured_machines,expected_name,reads", [
    (None, "Lathe", 1), ([], None, 0), ([{"machine_id": "other", "name": "Other machine"}], None, 0)])
def test_plan_details_respect_complete_machine_capture(dashboard_case, captured_machines, expected_name, reads):
    case, sql = dashboard_case, []
    plan_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=1 AND active=1").fetchone()[0]
    case.conn.set_trace_callback(sql.append)
    with WorkbenchPlanQueryService(case.conn).read_snapshot():
        context = PlanReadContext(case.conn, captured_machines=captured_machines)
        with context.read_scope():
            _, entry, _ = context.selected(plan_ref)
            row, = context.detail_rows(entry)
    assert row["machine_name"] == expected_name and row["operator_name"] == "Operator"
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum("FROM MACHINES " in statement for statement in normalized) == reads


def test_captured_calendar_preserves_sql_status_time_types_order_and_budget():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    register_schedule_time_sql_functions(conn)
    conn.executescript("""CREATE TABLE Machines(machine_id TEXT,name TEXT,status TEXT,op_type_id TEXT);
        CREATE TABLE MachineDowntimes(id INTEGER PRIMARY KEY,machine_id TEXT,start_time,end_time,status);
        CREATE TABLE SchemaVersion(id INTEGER,version INTEGER);
        INSERT INTO SchemaVersion VALUES(1,35); INSERT INTO Machines VALUES('M1','Lathe','active','T1');""")
    rows = [("M1", "2026-09-10T08:00:00", "2026-09-10T10:00:00", "active"),
            ("M1", "2026-09-10T09:00:00", "2026-09-10T11:00:00", "active"),
            ("M1", "2026-09-10T09:00:00", "2026-09-10T11:00:00", "cancelled"),
            ("M2", "2026-09-10T09:00:00", "2026-09-10T11:00:00", "active")]
    conn.executemany("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES(?,?,?,?)", rows)
    parsed = []

    def parse_once(value):
        parsed.append(value)
        return parse_dt_for_sql(value)

    conn.create_function(SQL_PARSE_FUNCTION, 1, parse_once)
    repo = DashboardSourceRepository(conn)
    raw, prepared = repo.downtime_capture(machine_ids=["M1"])
    # Two admitted rows, each endpoint once inside SQLite; cancelled/unselected rows stay unparsed.
    assert sorted(parsed) == sorted([rows[0][1], rows[0][2], rows[1][1], rows[1][2]])
    captured = CapturedCalendarInputs(machines=repo.table("Machines"), downtimes=prepared,
        schema_version=repo.table("SchemaVersion"), downtime_machine_ids=["M1"])
    expected = CalendarFactsRepository(conn).downtimes(["M1"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100)
    assert captured.downtimes(["M1"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100) == expected
    assert [tuple(row[key] for key in ("machine_id", "start_time", "end_time", "status")) for row in raw] == rows
    limited = CalendarFacts(conn, captured=captured)
    limited.count = 49999
    with pytest.raises(ProjectionLimit, match="calendar_fact_limit"):
        limited.read_downtimes(["M1"], "2026-09-10T09:00:00", "2026-09-10T11:00:00")
    assert "downtimes" not in limited.rows
    with pytest.raises(ProjectionLimit, match="calendar_unavailable"):
        captured.downtimes(["M2"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100)
    conn.close()


def test_captured_calendar_orders_mixed_storage_types_like_the_calendar_sql():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    register_schedule_time_sql_functions(conn)
    conn.execute("CREATE TABLE MachineDowntimes(id INTEGER PRIMARY KEY,machine_id TEXT,start_time,end_time,status)")
    rows = [("M1", "2026-09-10T09:00:00", "2026-09-10T10:00:00", "active"),
            ("M1", 20260910, "2026-09-10T10:00:00", "active"),
            ("M1", sqlite3.Binary(b"2026-09-10 08:00:00"), "2026-09-10T08:30:00", "active"),
            ("M1", sqlite3.Binary(b"\xff\xfe2026"), "2026-09-10T10:00:00", "active"),
            ("M1", 1.5, "2026-09-10T10:00:00", None),
            ("M1", "2026-09-10T08:00:00", sqlite3.Binary(b"2026-09-10 09:00:00"), "active"),
            ("M1", "2026-09-10T08:00:00", "2026-09-10T09:00:00", "weird")]
    conn.executemany("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES(?,?,?,?)", rows)
    raw, prepared = DashboardSourceRepository(conn).downtime_capture(machine_ids=["M1"])
    assert [row["id"] for row in raw] == list(range(1, len(rows) + 1))
    captured = CapturedCalendarInputs(machines=[], downtimes=prepared, schema_version=[], downtime_machine_ids=["M1"])
    window = ("2026-09-10T11:00:00", "2026-09-10T07:00:00")
    expected_capture = CalendarFactsRepository(conn).downtimes(["M1"], *window, limit=100)
    assert captured.downtimes(["M1"], *window, limit=100) == expected_capture
    assert [(row["start_time"], row["end_time"]) for row in expected_capture] == [(row[1], row[2]) for row in rows]
    admitted = CalendarFacts(conn).read_downtimes(["M1"], window[1], window[0])
    assert CalendarFacts(conn, captured=captured).read_downtimes(["M1"], window[1], window[0]) == admitted
    # SQLite's storage-class order after admission: numbers, then TEXT, then BLOB; equal starts by end, TEXT before BLOB.
    assert [(row["start_time"], row["end_time"]) for row in admitted] == [
        (rows[index][1], rows[index][2]) for index in (4, 1, 6, 5, 0, 2, 3)]
    conn.close()


def test_mixed_storage_downtimes_on_a_plan_machine_read_like_the_calendar_sql(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import NOW, api

    case = dashboard_case
    case.conn.executemany("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail) VALUES ('DM1',?,?,?)",
                          [(20260909, "2026-09-09T11:00:00", "integer"),
                           (sqlite3.Binary(b"2026-09-09 08:30:00"), "2026-09-09T09:30:00", "utf8 blob"),
                           (sqlite3.Binary(b"\xff\xfe2026"), "2026-09-09T11:00:00", "non-utf8 blob")])
    case.conn.commit()
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    window = ("2026-09-10T00:00:00", "2026-09-09T00:00:00")
    with reader.read_snapshot():
        facts = reader.load().facts
        expected = CalendarFactsRepository(case.conn).downtimes(["DM1"], *window, limit=100)
        admitted = CalendarFacts(case.conn).read_downtimes(["DM1"], window[1], window[0])
    assert facts.plan_state == "loaded" and len(expected) == 4
    assert facts.calendar_inputs.downtimes(["DM1"], *window, limit=100) == expected
    assert CalendarFacts(case.conn, captured=facts.calendar_inputs).read_downtimes(["DM1"], window[1], window[0]) == admitted
    client = api(case, monkeypatch)
    for path, params in (("/api/workbench/v1/dashboard", {}), ("/api/workbench/v1/dashboard/analysis", {"section": "downtime"})):
        response = client.get(path, query_string=params)
        assert response.status_code == 200, response.get_json()


def test_downtime_capture_avoids_temp_btree_and_unifies_admitted_resource_projections(dashboard_case):
    case = dashboard_case
    for marks, keys in (("?", ("DM1",)), ("?,?", ("DM1", "DM2"))):
        plan_rows = case.conn.execute(
            "EXPLAIN QUERY PLAN " + _DOWNTIMES_SQL.format(marks=marks) + " LIMIT ?",
            (*keys, "2026-09-10T00:00:00", "2026-09-09T00:00:00", 1),
        ).fetchall()
        assert all("TEMP B-TREE" not in " ".join(str(col) for col in row).upper() for row in plan_rows), plan_rows

    case.conn.executemany(
        "INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status,reason_detail) VALUES ('DM1',?,?,'active',?)",
        [
            ("2026-09-09T15:00:00", "2026-09-09T16:00:00", "Afternoon calibration"),
            ("2026-09-09T10:00:00", "2026-09-09T12:00:00", "Late morning overlap"),
            ("2026-09-09T08:00:00", "2026-09-09T09:30:00", "Early morning overlap"),
        ],
    )
    case.conn.commit()

    repo = DashboardSourceRepository(case.conn)
    _, prepared = repo.downtime_capture(machine_ids=["DM1"])
    captured = CapturedCalendarInputs(
        machines=repo.table("Machines"),
        downtimes=prepared,
        schema_version=repo.table("SchemaVersion"),
        downtime_machine_ids=["DM1"],
    )
    start_str, end_str = "2026-09-09T00:00:00", "2026-09-10T00:00:00"
    direct_head = CalendarFactsRepository(case.conn).downtimes(["DM1"], end_str, start_str, limit=2)
    assert captured.downtimes(["DM1"], end_str, start_str, limit=2) == direct_head
    assert [(row["start_time"], row["end_time"]) for row in direct_head] == [
        ("2026-09-09T09:00:00", "2026-09-09T11:00:00"),
        ("2026-09-09T15:00:00", "2026-09-09T16:00:00"),
    ]

    first, last = date(2026, 9, 8), date(2026, 9, 9)
    start, end = datetime(2026, 9, 9, 0, 0), datetime(2026, 9, 10, 0, 0)
    expected_sorted = [
        ("2026-09-09T08:00:00", "2026-09-09T09:30:00"),
        ("2026-09-09T09:00:00", "2026-09-09T11:00:00"),
        ("2026-09-09T10:00:00", "2026-09-09T12:00:00"),
        ("2026-09-09T15:00:00", "2026-09-09T16:00:00"),
    ]
    expected_merged = [
        {"start": datetime(2026, 9, 9, 8, 0), "end": datetime(2026, 9, 9, 12, 0)},
        {"start": datetime(2026, 9, 9, 15, 0), "end": datetime(2026, 9, 9, 16, 0)},
    ]
    projections = []
    for mode in ("resources", "resource_states"):
        for source in (None, captured):
            reader = CalendarFacts(case.conn, captured=source)
            reader.calendar(first.isoformat(), last.isoformat(), ["DO1"])
            if mode == "resources":
                reader.resources(["DM1"], ["DO1"], [case.op], start, end)
            else:
                reader.resource_states(["DM1"], ["DO1"], start, end)
            assert [(row["start_time"], row["end_time"]) for row in reader.rows["downtimes"]] == expected_sorted
            engine = SnapshotCalendarEngine(reader.rows)
            projected = {
                (kind, key): item
                for kind, key, _raw, item in project_resource_calendars(
                    engine, reader.rows, {"machine": ["DM1"], "operator": ["DO1"]}, first, last, start, end
                )
            }
            assert projected["machine", "DM1"]["downtime_windows"] == expected_merged
            projections.append(projected["machine", "DM1"])
    assert all(item == projections[0] for item in projections[1:])


def test_nonrisk_tasks_share_complete_machine_downtime_identity_evidence():
    from tests.workbench.dashboard_support import NOW
    records = [
        {"id": 1, "machine_id": "M1", "status": "cancelled", "start_time": "2020-01-01T08:00:00",
         "end_time": "2020-01-01T09:00:00", "reason_detail": "Cancelled history"},
        {"id": 2, "machine_id": "M1", "status": "active", "start_time": "2020-01-02T08:00:00",
         "end_time": "2020-01-02T09:00:00", "reason_detail": "Earlier maintenance"},
    ]
    identities = [{"source_id": source_id, "ref": format(index, "048x"), "active": active}
                  for index, (source_id, active) in enumerate(((1, 1), (1, 0), (2, 1)), start=1)]
    task = {"plan_ref": "a" * 48, "operation_ref": "b" * 48, "machine_ref": "c" * 48,
            "start": "2026-10-17T08:00:00", "end": "2026-10-17T09:00:00", "batch_id": "B1", "process_label": "Turning"}
    facts = facts_module.DashboardFacts(None, NOW)
    facts.plan_state = "loaded"
    facts.tasks = [dict(task, task_ref=format(index, "048x")) for index in range(10, 13)]
    facts.task_rows = [{"schedule_id": index, "source": "internal", "machine_id": key}
                       for index, key in enumerate(("M1", "M1", "M2"), start=1)]
    facts.task_intervals = {index: (datetime(2026, 10, 17, 8), datetime(2026, 10, 17, 9)) for index in range(1, 4)}
    facts.raw = {"MachineDowntimes": records, "WorkbenchDashboardDowntimeRefs": identities,
                 "Machines": [{"machine_id": key} for key in ("M1", "M2")]}
    rows, state = downtime.downtime(facts)
    assert state["assessed_count"] == 3 and all(row["risk"]["active"] is False for row in rows)
    first, second, other = (row["_facts"] for row in rows)
    assert first["downtimes"] == records and first["identity"] == identities
    assert first["identity"] is second["identity"]
    assert other["identity"] == other["downtimes"] == []


@pytest.mark.parametrize("section", ["delivery", "downtime"])
def test_analysis_records_counts_and_overlaps_share_one_downtime_parse(dashboard_case, monkeypatch, section):
    from tests.workbench.dashboard_support import NOW

    built, original = [], downtime.downtime_index

    def tracked(raw, refs):
        built.append(len(raw))
        return original(raw, refs)

    monkeypatch.setattr(downtime, "downtime_index", tracked)
    data, _ = read_dashboard_analysis(dashboard_case.conn, query=DashboardAnalysisQuery(section), as_of=NOW)
    assert built == [1]
    assert (data["pagination"]["totals"]["downtimes"], data["pagination"]["totals"]["overlaps"]) == (1, 1)


def test_unreadable_downtime_end_keeps_its_start_and_leaves_the_overlap_unknown(dashboard_case):
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    case.conn.execute("UPDATE MachineDowntimes SET end_time='not a time'")
    case.conn.commit()
    data, _ = read_dashboard_analysis(case.conn, query=DashboardAnalysisQuery("downtime"), as_of=NOW)
    record, = data["downtimes"]
    assert (record["start"], record["end"], record["valid"]) == ("2026-09-09T09:00:00", None, False)
    assert "downtime_invalid" in [issue["code"] for issue in data["issues"]]
    assert data["pagination"]["totals"]["downtimes"] == 1 and data["overlaps"] == []
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        facts = reader.load().facts
    rows, state = facts.observations("downtime")
    assert [row["risk"]["code"] for row in rows] == ["downtime_unknown"] and state["unknown_count"] == 1


def test_non_utf8_blob_downtime_is_an_invalid_row_not_a_read_failure(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import api

    case = dashboard_case
    case.conn.execute("UPDATE MachineDowntimes SET start_time=?", (sqlite3.Binary(b"\xff\xfe2026"),))
    case.conn.commit()
    client = api(case, monkeypatch)
    listed = client.get("/api/workbench/v1/dashboard")
    assert listed.status_code == 200, listed.get_json()
    downtime_row = listed.get_json()["data"]["categories"]["downtime"]
    assert downtime_row["unknown_count"] == 1
    analyzed = client.get("/api/workbench/v1/dashboard/analysis", query_string={"section": "downtime"})
    assert analyzed.status_code == 200, analyzed.get_json()
    data = analyzed.get_json()["data"]
    record, = data["downtimes"]
    assert (record["start"], record["end"], record["valid"]) == (None, "2026-09-09T11:00:00", False)
    assert "downtime_invalid" in [issue["code"] for issue in data["issues"]]


def test_stale_snapshot_rejects_before_loading_sources_and_projects_outside_transaction(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import api, connect

    case, sql, in_tx = dashboard_case, [], []
    original_project = facts_module.DashboardFacts.project

    def tracked_project(facts):
        in_tx.append(facts.conn.in_transaction)
        return original_project(facts)

    monkeypatch.setattr(facts_module.DashboardFacts, "project", tracked_project)

    def traced_connect(path):
        conn = connect(path)
        conn.set_trace_callback(sql.append)
        return conn

    client = api(case, monkeypatch, connect_factory=traced_connect)
    listed = client.get("/api/workbench/v1/dashboard")
    assert listed.status_code == 200, listed.get_json()
    list_token = listed.get_json()["meta"]["snapshot_ref"]
    analyzed = client.get("/api/workbench/v1/dashboard/analysis", query_string={"section": "delivery"})
    assert analyzed.status_code == 200, analyzed.get_json()
    analysis_token = analyzed.get_json()["meta"]["snapshot_ref"]
    assert in_tx and all(flag is False for flag in in_tx)

    case.conn.execute("UPDATE Materials SET remark='updated remark' WHERE material_id='DMAT'")
    case.conn.commit()

    for path, params in (
        ("/api/workbench/v1/dashboard", {"snapshot_ref": list_token}),
        ("/api/workbench/v1/dashboard/analysis", {"section": "delivery", "snapshot_ref": analysis_token}),
    ):
        sql.clear()
        in_tx.clear()
        stale = client.get(path, query_string=params)
        assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
        selects = [stmt for stmt in sql if stmt.lstrip().upper().startswith("SELECT")]
        assert 1 <= len(selects) <= 2, selects
        assert all("WORKBENCHSOURCEREVISIONS" in stmt.upper() for stmt in selects), selects
        assert in_tx == []
