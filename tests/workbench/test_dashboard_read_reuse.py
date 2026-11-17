"""One dashboard capture supplies its projections and calendar source reads."""

import json
from collections import Counter
from datetime import date, datetime, timedelta

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.services.capacity.plan_calendar_io import MAX_FACT_ROWS, CalendarFacts, ProjectionLimit
from core.services.capacity.plan_calendar_windows import project_resource_calendars
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.workbench.dashboard import calendar_capture, downtime
from core.services.workbench.dashboard import facts as facts_module
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.dashboard.analysis_projection import project_dashboard_analysis
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_facts
from core.shared.local_datetime import datetime_to_us
from data.repositories.calendar_facts_repo import _DOWNTIMES_SQL, CalendarFactsRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


@pytest.fixture
def dashboard_case(tmp_path):
    from tests.workbench.dashboard_support import dashboard_case as existing_case
    yield from existing_case.__wrapped__(tmp_path)


def test_one_capture_reuses_projections_and_only_reads_new_identity_keys(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import NOW
    case, calls, keys, sql = dashboard_case, Counter(), [], []
    for name in ("actual", "downtime"):
        original = getattr(facts_module, name)

        def tracked(*args, _name=name, _original=original):
            calls[_name] += 1
            return _original(*args)

        monkeypatch.setattr(facts_module, name, tracked)
    original_refs = WorkbenchIdentityRepository.active_map

    def refs(repo, kind, requested):
        keys.append((kind, list(requested)))
        return original_refs(repo, kind, requested)

    monkeypatch.setattr(WorkbenchIdentityRepository, "active_map", refs)
    case.conn.set_trace_callback(sql.append)
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot():
        sources = reader.load(NOW)
        facts, material = sources.facts, sources.material
        assert facts.plan_state == "loaded" and len(facts.tasks) == 1
        assert facts.entity_refs("batch", ["DB1"]) == facts.entity_refs("batch", ["DB1"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["DB1", "missing-batch"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["missing-batch"])
    monkeypatch.setattr(facts_module, "candidate_catalog", lambda _: pytest.fail("Analysis read candidate catalog"))
    data = reader.project(sources)
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
    assert sum("FROM SCHEMAVERSION " in statement for statement in normalized) == 1


def _us(*args):
    return datetime_to_us(datetime(*args))


def _iso_us(text):
    return datetime_to_us(datetime.fromisoformat(text))


def test_captured_rows_count_against_the_same_calendar_fact_budget(schema_conn):
    reader = CalendarFacts(schema_conn)
    reader.count = MAX_FACT_ROWS - 2
    reader.captured("machines", [{"machine_id": "M1"}])
    with pytest.raises(ProjectionLimit, match="calendar_fact_limit"):
        reader.captured("downtimes", [{"machine_id": "M1"}, {"machine_id": "M1"}])
    assert "downtimes" not in reader.rows and reader.count == MAX_FACT_ROWS - 1


def test_dashboard_calendar_takes_the_calendar_downtime_set_from_its_one_capture(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('DM2','Mill')")
    rows = [("DM1", 8, 9, "cancelled"), ("DM1", 6, 7, "active"), ("DM1", 8, 8, "active"), ("DM2", 8, 9, "active")]
    case.conn.executemany(
        "INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,reason_code,status) "
        "VALUES (?,?,?,?,?,'maintenance',?)",
        [(machine, f"2026-09-09 {start:02d}:00:00", f"2026-09-09 {end:02d}:30:00", _us(2026, 9, 9, start),
          _us(2026, 9, 9, end, 30), status) for machine, start, end, status in rows])
    case.conn.commit()
    seen, original = [], calendar_capture.calendar_from_sources

    def tracked(sources, **kwargs):
        seen.append(sources)
        return original(sources, **kwargs)

    monkeypatch.setattr(calendar_capture, "calendar_from_sources", tracked)
    sql = []
    case.conn.set_trace_callback(sql.append)
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot():
        sources = reader.load(NOW)
    case.conn.set_trace_callback(None)
    captured, = seen
    scope = sources.facts.pressure["time_scope"]
    start, end = datetime.fromisoformat(scope["range_start"]), datetime.fromisoformat(scope["range_end"])
    expected = CalendarFactsRepository(case.conn).downtimes(["DM1"], end, start, limit=100)
    # Only the window's machine, its active rows that overlap the window: the calendar repository's own condition.
    assert len(expected) == 2
    assert (sorted((row["machine_id"], row["start_us"], row["end_us"]) for row in captured["downtimes"])
            == sorted((row["machine_id"], row["start_us"], row["end_us"]) for row in expected))
    assert [row["machine_id"] for row in captured["machines"]] == ["DM1"]
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum("FROM MACHINEDOWNTIMES " in statement for statement in normalized) == 1


def test_downtime_reads_avoid_temp_btree_and_both_read_modes_project_the_same_windows(dashboard_case):
    case = dashboard_case
    for keys in (("DM1",), ("DM1", "DM2")):
        plan_rows = case.conn.execute(
            "EXPLAIN QUERY PLAN " + _DOWNTIMES_SQL,
            (json.dumps(list(keys)), _us(2026, 9, 10), _us(2026, 9, 9)),
        ).fetchall()
        assert all("TEMP B-TREE" not in " ".join(str(col) for col in row).upper() for row in plan_rows), plan_rows

    case.conn.executemany(
        "INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,status,reason_code,reason_detail) "
        "VALUES ('DM1',?,?,?,?,'active','maintenance',?)",
        [
            ("2026-09-09 15:00:00", "2026-09-09 16:00:00", _us(2026, 9, 9, 15), _us(2026, 9, 9, 16), "Afternoon calibration"),
            ("2026-09-09 10:00:00", "2026-09-09 12:00:00", _us(2026, 9, 9, 10), _us(2026, 9, 9, 12), "Late morning overlap"),
            ("2026-09-09 08:00:00", "2026-09-09 09:30:00", _us(2026, 9, 9, 8), _us(2026, 9, 9, 9, 30), "Early morning overlap"),
        ],
    )
    case.conn.commit()

    first, last = date(2026, 9, 8), date(2026, 9, 9)
    start, end = datetime(2026, 9, 9, 0, 0), datetime(2026, 9, 10, 0, 0)
    expected_sorted = [
        (_us(2026, 9, 9, 8), _us(2026, 9, 9, 9, 30)),
        (_us(2026, 9, 9, 9), _us(2026, 9, 9, 11)),
        (_us(2026, 9, 9, 10), _us(2026, 9, 9, 12)),
        (_us(2026, 9, 9, 15), _us(2026, 9, 9, 16)),
    ]
    direct_head = CalendarFactsRepository(case.conn).downtimes(["DM1"], end, start, limit=2)
    assert [(row["start_us"], row["end_us"]) for row in direct_head] == expected_sorted[:2]
    expected_merged = [
        {"start": datetime(2026, 9, 9, 8, 0), "end": datetime(2026, 9, 9, 12, 0)},
        {"start": datetime(2026, 9, 9, 15, 0), "end": datetime(2026, 9, 9, 16, 0)},
    ]
    projections = []
    for mode in ("resources", "resource_states"):
        reader = CalendarFacts(case.conn)
        reader.calendar(first.isoformat(), last.isoformat(), ["DO1"])
        if mode == "resources":
            reader.resources(["DM1"], ["DO1"], [case.op], start, end)
        else:
            reader.resource_states(["DM1"], ["DO1"], start, end)
        assert [(row["start_us"], row["end_us"]) for row in reader.rows["downtimes"]] == expected_sorted
        engine = CalendarEngine(calendar_inputs_from_facts(reader.rows))
        projected = {
            (kind, key): item
            for kind, key, _raw, item in project_resource_calendars(
                engine, reader.rows, {"machine": ["DM1"], "operator": ["DO1"]}, first, last, start, end
            )
        }
        assert projected["machine", "DM1"]["downtime_windows"] == expected_merged
        projections.append(projected["machine", "DM1"])
    assert projections[0] == projections[1]


def test_nonrisk_tasks_share_complete_machine_downtime_identity_evidence():
    from tests.workbench.dashboard_support import NOW
    records = [
        {"id": 1, "machine_id": "M1", "status": "cancelled", "start_us": _us(2020, 1, 1, 8),
         "end_us": _us(2020, 1, 1, 9), "reason_detail": "Cancelled history"},
        {"id": 2, "machine_id": "M1", "status": "active", "start_us": _us(2020, 1, 2, 8),
         "end_us": _us(2020, 1, 2, 9), "reason_detail": "Earlier maintenance"},
    ]
    identities = [{"source_id": source_id, "ref": format(index, "048x"), "active": active, "revision": 1}
                  for index, (source_id, active) in enumerate(((1, 1), (1, 0), (2, 1)), start=1)]
    task = {"plan_ref": "a" * 48, "operation_ref": "b" * 48, "machine_ref": "c" * 48,
            "start": "2026-10-17T08:00:00", "end": "2026-10-17T09:00:00", "batch_id": "B1", "process_label": "Turning"}
    facts = facts_module.DashboardFacts(None, NOW)
    facts.plan_state = "loaded"
    facts.tasks = [dict(task, task_ref=format(index, "048x")) for index in range(10, 13)]
    facts.task_rows = [{"schedule_id": index, "source": "internal", "machine_id": key,
                        "start_us": _us(2026, 10, 17, 8), "end_us": _us(2026, 10, 17, 9)}
                       for index, key in enumerate(("M1", "M1", "M2"), start=1)]
    facts.raw = {"MachineDowntimes": records, "WorkbenchDashboardDowntimeRefs": identities,
                 "Machines": [{"machine_id": key} for key in ("M1", "M2")]}
    rows, state = downtime.downtime(facts)
    assert state["assessed_count"] == 3 and all(row["risk"]["active"] is False for row in rows)
    assert all("_facts" not in row and "source_revision" in row["_guard"] for row in rows)
    assert rows[0]["_guard"]["source_revision"] != rows[2]["_guard"]["source_revision"]


@pytest.mark.parametrize("section", ["delivery", "downtime"])
def test_analysis_records_counts_and_overlaps_share_one_downtime_parse(dashboard_case, monkeypatch, section):
    from tests.workbench.dashboard_support import NOW

    built, original = [], downtime.downtime_index

    def tracked(raw, refs):
        built.append(len(raw))
        return original(raw, refs)

    monkeypatch.setattr(facts_module, "downtime_index", tracked)
    data, _ = read_dashboard_analysis(dashboard_case.conn, query=DashboardAnalysisQuery(section), as_of=NOW)
    assert built == [1]
    assert (data["pagination"]["totals"]["downtimes"], data["pagination"]["totals"]["overlaps"]) == (1, 1)


def test_dashboard_and_its_delivery_read_decode_the_plan_deferred_operations_once(dashboard_case, monkeypatch):
    """看板和它调用的交付读取共读同一版正式计划的延后清单：一次看板读取只解码一次，单条交付项读取也只解码一次。"""
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    case.conn.execute(
        "INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
        "VALUES (9001,'DOP2','DB1',2,'DT1','Turning','internal',0.5,0)"
    )
    deferred_text = "[9001]"
    case.conn.execute("UPDATE ScheduleHistory SET deferred_operation_ids_json=? WHERE version=1", (deferred_text,))
    case.conn.commit()
    decoded = []
    original_decode = json.JSONDecoder.decode

    def counted(decoder, text, *args, **kwargs):
        if text == deferred_text:
            decoded.append(text)
        return original_decode(decoder, text, *args, **kwargs)

    # 按文本计数：json.loads 与存储严格解码都经 JSONDecoder.decode，哪条路解都会被数到。
    monkeypatch.setattr(json.JSONDecoder, "decode", counted)
    data, _ = read_dashboard_analysis(case.conn, query=DashboardAnalysisQuery("delivery"), as_of=NOW)
    assert len(decoded) == 1
    delivery, = data["deliveries"]
    assert delivery["deferred_operation_count"] == 1

    decoded.clear()
    single = facts_module.DashboardFacts(case.conn, NOW)
    with WorkbenchDashboardService(case.conn).read_snapshot():
        single.load_plan_item({"category": "delivery", "batch_ref": delivery["batch_ref"]})
    assert len(decoded) == 1
    assert [item["deferred_operation_count"] for item in single.delivery_items] == [1]


def test_single_material_item_reads_its_batch_identity_once_by_ref(dashboard_case):
    """单条齐套项按条目里的永久编号读一次批次身份；随后按批次号找身份直接用这一次读到的，不按业务键再查。"""
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot():
        item = next(row for row in reader.read(NOW)["items"] if row["category"] == "material")
    sql = []
    case.conn.set_trace_callback(sql.append)
    with reader.read_snapshot():
        single = reader.read_command_item(item["item_ref"], NOW)
    case.conn.set_trace_callback(None)
    identity_reads = [stmt for stmt in sql if "FROM WorkbenchEntityRefs" in stmt]
    assert not any("kind = 'batch'" in stmt for stmt in identity_reads), identity_reads
    assert sum(" WHERE ref = " in stmt for stmt in identity_reads) == 1
    assert single["item_ref"] == item["item_ref"] and single["source_state"] == "current"


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

    client = api(case, connect_factory=traced_connect)
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


def test_downtime_binary_search_finds_enclosing_interval_and_preserves_capture_order():
    from tests.workbench.dashboard_support import NOW

    records = [
        {"id": 10, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T09:30:00"),
         "end_us": _iso_us("2026-10-17T10:30:00"), "reason_detail": "Captured first"},
        {"id": 11, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T08:00:00"),
         "end_us": _iso_us("2026-10-17T18:00:00"), "reason_detail": "Long enclosing downtime"},
        {"id": 12, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T08:10:00"),
         "end_us": _iso_us("2026-10-17T08:20:00"), "reason_detail": "Nested early 1"},
        {"id": 13, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T08:30:00"),
         "end_us": _iso_us("2026-10-17T08:40:00"), "reason_detail": "Nested early 2"},
        {"id": 14, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T09:15:00"),
         "end_us": _iso_us("2026-10-17T09:45:00"), "reason_detail": "Left touching"},
        {"id": 15, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T10:15:00"),
         "end_us": _iso_us("2026-10-17T10:45:00"), "reason_detail": "Right touching"},
        {"id": 16, "machine_id": "M1", "status": "active", "start_us": _iso_us("2026-10-17T10:00:00"),
         "end_us": _iso_us("2026-10-17T10:20:00"), "reason_detail": "Partial overlap"},
    ]
    identities = [
        {"source_id": row["id"], "ref": format(row["id"], "048x"), "active": 1, "revision": 1}
        for row in records
    ]
    base_task = {"plan_ref": "a" * 48, "operation_ref": "b" * 48, "machine_ref": "c" * 48, "batch_id": "B1", "process_label": "Turning"}
    facts = facts_module.DashboardFacts(None, NOW)
    facts.plan_state = "loaded"
    facts.tasks = [
        {**base_task, "task_ref": format(1, "048x"), "start": "2026-10-17T15:00:00", "end": "2026-10-17T16:00:00"},
        {**base_task, "task_ref": format(2, "048x"), "start": "2026-10-17T09:45:00", "end": "2026-10-17T10:15:00"},
    ]
    facts.task_rows = [
        {"schedule_id": 1, "source": "internal", "machine_id": "M1",
         "start_us": _us(2026, 10, 17, 15, 0), "end_us": _us(2026, 10, 17, 16, 0)},
        {"schedule_id": 2, "source": "internal", "machine_id": "M1",
         "start_us": _us(2026, 10, 17, 9, 45), "end_us": _us(2026, 10, 17, 10, 15)},
    ]
    facts.raw = {
        "MachineDowntimes": records,
        "WorkbenchDashboardDowntimeRefs": identities,
        "Machines": [{"machine_id": "M1"}],
    }
    assert downtime.downtime_overlap_count(facts) == 2
    rows, state = downtime.downtime(facts)
    assert state["assessed_count"] == 2
    tail_hit, multi_hit = rows
    assert tail_hit["source"]["known_overlap_hours"] == 1.0
    assert [item["downtime_ref"] for item in tail_hit["source"]["downtimes"]] == [format(11, "048x")]
    assert tail_hit["source"]["downtimes"][0]["overlap_start"] == "2026-10-17T15:00:00"
    assert tail_hit["source"]["downtimes"][0]["overlap_end"] == "2026-10-17T16:00:00"
    # Preserves original raw capture order (10, 11, 16) and union hours (0.5h) while excluding touching windows (14, 15).
    assert multi_hit["source"]["known_overlap_hours"] == 0.5
    assert [item["downtime_ref"] for item in multi_hit["source"]["downtimes"]] == [
        format(10, "048x"),
        format(11, "048x"),
        format(16, "048x"),
    ]
    assert multi_hit["source"]["downtimes"][2]["overlap_start"] == "2026-10-17T10:00:00"
    assert multi_hit["source"]["downtimes"][2]["overlap_end"] == "2026-10-17T10:15:00"

    class _CountedSeq:
        def __init__(self, items, counter):
            self._items = items
            self._counter = counter

        def __iter__(self):
            self._counter[0] += len(self._items)
            return iter(self._items)

        def __getitem__(self, item):
            sliced = self._items[item]
            self._counter[0] += len(sliced)
            return sliced

    def _wrap_tree(node, counter):
        if node is None:
            return None
        center, span_starts, by_start, span_ends, by_end, left, right = node
        return (
            center,
            span_starts,
            _CountedSeq(by_start, counter),
            span_ends,
            _CountedSeq(by_end, counter),
            _wrap_tree(left, counter),
            _wrap_tree(right, counter),
        )

    first = datetime(2026, 1, 1)
    bulk_records = [
        {"id": 1, "machine_id": "M1", "status": "active", "start_us": datetime_to_us(first),
         "end_us": datetime_to_us(first + timedelta(minutes=10000)), "reason_detail": "Full-span enclosing"}
    ]
    for n in range(1, 5000):
        start = first + timedelta(minutes=2 * n)
        bulk_records.append({
            "id": n + 1, "machine_id": "M1", "status": "active",
            "start_us": datetime_to_us(start), "end_us": datetime_to_us(start + timedelta(minutes=1)),
            "reason_detail": "Short window",
        })
    bulk_identities = [{"source_id": n, "ref": format(n, "048x"), "active": 1, "revision": 1} for n in range(1, 5001)]
    bulk_facts = facts_module.DashboardFacts(None, NOW)
    bulk_facts.plan_state = "loaded"
    bulk_facts.tasks = []
    bulk_facts.task_rows = []
    for n in range(1, 1001):
        start = first + timedelta(minutes=2 * n)
        end = start + timedelta(minutes=1)
        bulk_facts.tasks.append({
            **base_task, "task_ref": format(n, "048x"), "start": start.isoformat(), "end": end.isoformat(),
        })
        bulk_facts.task_rows.append({"schedule_id": n, "source": "internal", "machine_id": "M1",
                                     "start_us": datetime_to_us(start), "end_us": datetime_to_us(end)})
    bulk_facts.raw = {
        "MachineDowntimes": bulk_records,
        "WorkbenchDashboardDowntimeRefs": bulk_identities,
        "Machines": [{"machine_id": "M1"}],
    }
    assert downtime.downtime_overlap_count(bulk_facts) == 1000
    index = bulk_facts.downtime_index()
    starts, sorted_ends, tree = index["search"]["M1"]
    candidate_hits = [0]
    index["search"]["M1"] = (starts, sorted_ends, _wrap_tree(tree, candidate_hits))
    bulk_rows, bulk_state = downtime.downtime(bulk_facts)
    assert bulk_state["assessed_count"] == 1000
    assert candidate_hits[0] == 2000
    assert sum(len(row["source"]["downtimes"]) for row in bulk_rows) == 2000
    assert [item["downtime_ref"] for item in bulk_rows[0]["source"]["downtimes"]] == [
        format(1, "048x"),
        format(2, "048x"),
    ]


def test_report_catalog_and_calibration_exports_reject_invalid_format_before_snapshot_or_slot(monkeypatch):
    from flask import Blueprint, Flask

    from web.routes.workbench import calibration as calibration_routes
    from web.routes.workbench import reports_catalog
    from web.routes.workbench.calibration import register_calibration_routes
    from web.routes.workbench.read_budget import PLAN_READ_SLOTS
    from web.routes.workbench.reports import register_report_routes

    monkeypatch.setattr(reports_catalog, "read_snapshot_time", lambda *_: pytest.fail("Resolved report snapshot before format check"))
    monkeypatch.setattr(calibration_routes, "resolve_read_snapshot", lambda *_: pytest.fail("Resolved calibration snapshot before format check"))
    monkeypatch.setattr(PLAN_READ_SLOTS, "slot", lambda *_: pytest.fail("Acquired PLAN_READ_SLOTS before format check"))

    app = Flask("export-format-gate")
    app.config.update(TESTING=True, SECRET_KEY="temporary-export-format-gate")
    bp = Blueprint("workbench_export_format_gate", __name__)
    register_report_routes(bp)
    register_calibration_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()

    report_resp = client.get("/api/workbench/v1/reports/downtime/export", query_string={"snapshot_ref": "unverified", "format": "pdf"})
    report_body = report_resp.get_json()
    assert report_resp.status_code == 400 and report_body["error"]["code"] == "invalid_input"
    assert report_body["error"]["message"] == "只能导出 CSV 或 XLSX，没有开始下载。请重新选择格式。"

    cal_resp = client.get("/api/workbench/v1/calibration/export", query_string={"snapshot_ref": "unverified", "format": "pdf"})
    cal_body = cal_resp.get_json()
    assert cal_resp.status_code == 400 and cal_body["error"]["code"] == "invalid_input"
    assert cal_body["error"]["message"] == "只支持 CSV 或 XLSX 格式。"
