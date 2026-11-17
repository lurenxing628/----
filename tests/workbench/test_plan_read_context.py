"""One request captures plan facts once and keeps input bindings strict."""

import json
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS, OperationEffort
from core.models.content import StoredJsonCorrupt
from core.models.workbench_plan_scope import PlanReadScope
from core.services.capacity.plan_calendar_io import CalendarFacts
from core.services.workbench.plan import calendar_context, projection, queries
from core.services.workbench.plan import read_context as read_context_mod
from core.services.workbench.plan.calendar import project_plan_calendar
from core.services.workbench.plan.read_context import PlanReadContext
from core.shared.local_datetime import datetime_to_us
from core.shared.strict_json import canonical_json
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from tests._support.gantt_current_js import run_current_js
from tests.workbench.plan_catalog_support import insert_schedule_rows, update_schedule_rows
from tests.workbench.plan_read_support import (  # noqa: F401
    NIGHT_END,
    NIGHT_START,
    add_tasks,
    assert_error,
    plan_read_api,
)
from tests.workbench.plan_transport_support import follow_up_fixture, run_probe, workspace_fixture


def test_read_context_owns_capture_and_next_request_observes_change(plan_api, monkeypatch):
    with plan_api.db() as conn:
        add_tasks(conn, 1, start="2026-09-10T08:00:00", end="2026-09-10T09:00:00")
    ref, captures, selected_calls = plan_api.ref(), Counter(), []
    original_rows_fn = SchedulePlanQueryRepository.list_schedule_rows
    selected = calendar_context.selected_context

    def storage_rows(repo, *, version, range_start_us=None, range_end_us=None):
        captures["raw", version, range_start_us is not None] += 1
        return original_rows_fn(repo, version=version, range_start_us=range_start_us, range_end_us=range_end_us)

    def selection(*args, **kwargs):
        result = selected(*args, **kwargs)
        selected_calls.append((args[0].plan_ref, result))
        return result

    monkeypatch.setattr(SchedulePlanQueryRepository, "list_schedule_rows", storage_rows)
    monkeypatch.setattr(calendar_context, "selected_context", selection)
    scope = PlanReadScope(ref, NIGHT_START, NIGHT_END)
    with plan_api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        conn.execute("BEGIN")
        reader = queries.WorkbenchPlanQueryService(conn)
        statements, changes = [], conn.total_changes
        conn.set_trace_callback(statements.append)
        with reader.read_snapshot() as context:
            data, _ = reader.workspace(context, scope)
            entry, _ = context.selected(ref)
            rows = context.detail_rows(entry)
            tasks = context.projected_tasks(ref, rows, resources=context.resource_identities(rows))
            assert data["task_count"] == 1 and len(rows) == len(tasks) == 2
            assert data["tasks"][0] == tasks[0]
        conn.set_trace_callback(None)
        assert conn.total_changes == changes
        assert captures["raw", 3, False] == 1
        assert [item[0] for item in selected_calls] == [ref]
        captured_ctx = selected_calls[0][1]
        assert isinstance(captured_ctx, calendar_context.SelectedPlanContext)
        assert captured_ctx.calendar_days == (
            captured_ctx.start.date() - timedelta(days=1),
            (captured_ctx.end - timedelta(microseconds=1)).date(),
            3,
        )
        assert sum("FROM WorkbenchPlanIdentityClock WHERE singleton = 1" in sql for sql in statements) == 1
        assert not any("SELECT schema_version FROM pragma_schema_version" in sql for sql in statements)
        assert sum("FROM ScheduleHistory WHERE plan_ref = '" + ref + "'" in sql for sql in statements) == 1
        assert not any(sql.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}
                       for sql in statements)
    with plan_api.db() as conn:
        update_schedule_rows(
            conn, 3, where="op_id != 1",
            start_time="2026-09-11T08:00:00", end_time="2026-09-11T09:00:00",
        )
        update_schedule_rows(
            conn, 3, where="operator_id = 'PRIVATE-O1'",
            start_time="2026-09-11T11:00:00", end_time="2026-09-11T12:00:00",
        )
    ordered = plan_api.read("/" + ref + "/workspace")
    assert [t["start"] for t in ordered["data"]["tasks"]] == ["2026-09-11T08:00:00", "2026-09-11T11:00:00"]
    with plan_api.db() as conn:
        update_schedule_rows(
            conn, 3, where="operator_id = 'PRIVATE-O1'",
            start_time=NIGHT_START, end_time="2026-09-10T05:30:00",
        )
    changed = plan_api.read("/" + ref + "/workspace", range_start=NIGHT_START, range_end=NIGHT_END)
    assert changed["data"]["tasks"][0]["end"] == "2026-09-10T05:30:00"
    assert run_current_js(r"""
const M = h.module('PlanGanttModel.js'), taskFacts = M.prepareTasks(sourceData);
const occFacts = M.prepareOccupancy(sourceData, null, null, taskFacts.labels);
assert.strictEqual(occFacts.labels, taskFacts.labels, 'Initial prepareOccupancy reuses baseLabels without cloning');
const combined = M.combinePrepared(taskFacts, M.prepareBaseline(sourceData, taskFacts), occFacts);
assert.strictEqual(combined.labels, taskFacts.labels, 'Combined initial preparation keeps taskFacts.labels without cloning');
const sameOcc = M.prepareOccupancy(sourceData, occFacts, sourceData.projections.occupancy, taskFacts.labels);
assert.strictEqual(sameOcc.labels, taskFacts.labels, 'Projections with unchanged labels reuse baseLabels');
return true;
""", changed["data"])["result"] is True


def test_20k_saved_plan_is_selectable_and_one_day_reads_200_tasks_from_one_capture(plan_api, monkeypatch, record_property):
    with plan_api.db() as conn:
        first_extra = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM BatchOperations").fetchone()[0]
        extra_ids = list(range(first_extra, first_extra + 19999))
        conn.executemany(
            "INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'Extra op')",
            ((op, "EXTRA-" + str(op), op) for op in extra_ids),
        )
        conn.executemany(
            "INSERT INTO Machines(machine_id,name) VALUES (?,?)",
            [("M" + str(index), "Machine " + str(index)) for index in range(201)],
        )
        conn.executemany(
            "INSERT INTO Operators(operator_id,name) VALUES (?,?)",
            [("O" + str(index), "Operator " + str(index)) for index in range(201)],
        )
        operation_ids = [1] + extra_ids
        start = datetime(2026, 1, 1, 8)
        insert_schedule_rows(
            conn,
            4,
            [
                {
                    "op_id": operation_id,
                    "start_time": (start + timedelta(days=index // 200)).isoformat(),
                    "end_time": (start + timedelta(days=index // 200, hours=1)).isoformat(),
                    "machine_id": "M" + str(index % 201),
                    "operator_id": "O" + str(index % 201),
                }
                for index, operation_id in enumerate(operation_ids)
            ],
        )
    ref = plan_api.ref(4)
    with monkeypatch.context() as catalog_read:
        def no_full_capture(*args, **kwargs):
            pytest.fail("Catalog captured complete plan arrangements instead of streaming metadata")

        catalog_read.setattr(SchedulePlanQueryRepository, "list_schedule_rows", no_full_capture)
        catalog_read.setattr(SchedulePlanQueryRepository, "list_schedule_page", no_full_capture)
        catalog = plan_api.read(collection="history")["data"]["plans"]
    entry = next(row for row in catalog if row["plan_ref"] == ref)
    assert entry["capabilities"]["view"] and entry["capabilities"]["export"]
    assert entry["is_current_official"] and not entry["blocked_reasons"]
    whole = plan_api.read("/" + ref + "/workspace")["data"]
    assert whole["task_count"] == 20000 and len(whole["tasks"]) == queries.TASK_PAGE_SIZE
    assert whole["tasks_complete"] is False

    plan_api.statements.clear()
    scope = {"range_start": "2026-01-01T00:00:00", "range_end": "2026-01-02T00:00:00"}
    result = plan_api.read("/" + ref + "/workspace", **scope)
    data = result["data"]
    assert data["task_count"] == len(data["tasks"]) == 200 and data["tasks_complete"]
    delivery, = data["projections"]["delivery_risks"]["items"]
    assert delivery["operation_count"] == delivery["scheduled_operation_count"] == 20000
    statements = [sql.upper() for sql in plan_api.statements]
    captures = [sql for sql in statements if "FROM SCHEDULE S" in sql and "LEFT JOIN MACHINES" in sql]
    assert len(captures) == 1
    assert not any(sql.startswith("SELECT MACHINE_ID,NAME FROM MACHINES WHERE MACHINE_ID IN (") for sql in statements)
    assert not any(sql.startswith("SELECT OPERATOR_ID,NAME FROM OPERATORS WHERE OPERATOR_ID IN (") for sql in statements)
    record_property("complete_source_rows", 20000)
    record_property("visible_task_count", data["task_count"])
    record_property("source_capture_queries", len(captures))


def test_plan_endpoints_project_only_requested_slices_and_share_snapshot_state(plan_api, monkeypatch, tmp_path):
    with plan_api.db() as conn:
        first_extra = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM BatchOperations").fetchone()[0]
        extra_ids = list(range(first_extra, first_extra + 5000))
        conn.executemany(
            "INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name) VALUES (?,?,'CAT-B',?,'Extra op')",
            ((op, "EXTRA-" + str(op), op) for op in extra_ids),
        )
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('TAIL-M','Tail machine')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('TAIL-O','Tail operator')")
        operation_ids = [1] + extra_ids
        start = datetime(2026, 9, 9, 8)
        insert_schedule_rows(
            conn,
            4,
            [
                {
                    "op_id": operation_id,
                    "start_time": (start + timedelta(minutes=index)).isoformat(),
                    "end_time": (start + timedelta(minutes=index + 1)).isoformat(),
                    "machine_id": "TAIL-M" if index == 5000 else "PRIVATE-M1",
                    "operator_id": "TAIL-O" if index == 5000 else "PRIVATE-O1",
                }
                for index, operation_id in enumerate(operation_ids)
            ],
        )
    ref = plan_api.ref(4)
    projected_counts = []
    storage_calls = []
    page_calls = []
    original_project_tasks = projection.project_tasks
    original_storage_rows = SchedulePlanQueryRepository.list_schedule_rows
    original_page_rows = SchedulePlanQueryRepository.list_schedule_page

    def tracked_project_tasks(plan_ref, rows, *args, **kwargs):
        projected_counts.append(len(rows))
        return original_project_tasks(plan_ref, rows, *args, **kwargs)

    def tracked_storage_rows(repo, *, version, range_start_us=None, range_end_us=None):
        storage_calls.append(version)
        return original_storage_rows(repo, version=version, range_start_us=range_start_us, range_end_us=range_end_us)

    def tracked_page_rows(repo, *, version, range_start_us, range_end_us, limit, offset):
        page_calls.append((version, limit, offset))
        return original_page_rows(
            repo, version=version, range_start_us=range_start_us, range_end_us=range_end_us, limit=limit, offset=offset
        )

    monkeypatch.setattr(projection, "project_tasks", tracked_project_tasks)
    monkeypatch.setattr(read_context_mod, "project_tasks", tracked_project_tasks)
    monkeypatch.setattr(SchedulePlanQueryRepository, "list_schedule_rows", tracked_storage_rows)
    monkeypatch.setattr(SchedulePlanQueryRepository, "list_schedule_page", tracked_page_rows)
    whole = workspace_fixture(plan_api, "5001 tasks across pages", ref)
    workspace_res = whole["payload"]
    workspace_data = workspace_res["data"]
    token = workspace_res["meta"]["snapshot_ref"]
    assert workspace_data["task_count"] == 5001
    assert len(workspace_data["tasks"]) == 5000 and workspace_data["tasks_complete"] is False
    assert projected_counts == [5000]
    assert storage_calls == [4]
    assert {item["business_code"] for item in workspace_data["resources"]} >= {"TAIL-M", "TAIL-O"}

    projected_counts.clear()
    storage_calls.clear()
    page_calls.clear()
    with monkeypatch.context() as patch:
        for attr in (
            "build_plan_baseline",
            "project_plan_calendar",
            "project_plan_occupancy",
            "read_plan_delivery",
            "plan_gantt_graph",
        ):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"tasks_page called {attr}"))
        tasks_p2 = plan_api.read("/" + ref + "/tasks", snapshot_ref=token, page=2, size=5000)
    assert tasks_p2["meta"]["snapshot_ref"] == token
    assert tasks_p2["data"]["task_count"] == 5001
    assert len(tasks_p2["data"]["tasks"]) == 1 and tasks_p2["data"]["tasks_complete"] is False
    assert projected_counts == [1]
    assert page_calls == [(4, 5000, 5000)]
    assert storage_calls == []

    projected_counts.clear()
    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("project_plan_calendar", "project_plan_occupancy", "read_plan_delivery", "plan_gantt_graph"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"baseline_comparison called {attr}"))
        baseline = follow_up_fixture(plan_api, "5001-task baseline", whole, "baseline", page=1, size=5000)
    assert baseline["payload"]["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == []

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "project_plan_calendar", "project_plan_occupancy", "read_plan_delivery"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"gantt_graph called {attr}"))
        graph = follow_up_fixture(plan_api, "5001-task gantt graph", whole, "gantt_graph")
    assert graph["payload"]["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == []

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "read_plan_delivery", "plan_gantt_graph"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"capacity_projections called {attr}"))
        capacity = follow_up_fixture(plan_api, "5001-task capacity", whole, "capacity")
    assert capacity["payload"]["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == [4]
    # 前端读整份计划：首页之外的工序按页接上；跟进读取只核身份与范围，不再扫这 5001 道工序。
    whole["pages"] = [tasks_p2]
    whole["expected"] = deepcopy(workspace_res)
    whole["expected"]["data"]["tasks"] += tasks_p2["data"]["tasks"]
    whole["expected"]["data"]["tasks_complete"] = True
    run_probe(tmp_path, [whole, baseline, graph, capacity])

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "project_plan_calendar", "project_plan_occupancy", "plan_gantt_graph"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"export_workspace called {attr}"))
        export_res = plan_api.get("/" + ref + "/export", snapshot_ref=token, format="csv")
    assert export_res.status_code == 200
    assert export_res.headers["X-Workbench-Snapshot-Ref"] == token
    assert export_res.headers["X-Workbench-Row-Count"] == "5001"
    assert projected_counts == [5001]
    assert storage_calls == [4]

    storage_calls.clear()
    page_calls.clear()
    with plan_api.db() as conn:
        conn.execute("UPDATE Machines SET remark='Stale machine fact' WHERE machine_id='PRIVATE-M1'")
    assert_error(plan_api.get("/" + ref + "/tasks", snapshot_ref=token, page=2, size=5000), "snapshot_stale", status=409)
    assert storage_calls == [] and page_calls == []


def test_history_documents_decode_each_document_once_per_scope_and_only_when_read(plan_api, monkeypatch):
    deferred_text, algorithm_text = "[987654]", '{"mode":"improve"}'
    with plan_api.db() as conn:
        conn.execute(
            "UPDATE ScheduleHistory SET deferred_operation_ids_json=?, algorithm_json=? WHERE version=3",
            (deferred_text, algorithm_text),
        )
        policy_text = conn.execute("SELECT material_policy_json FROM ScheduleHistory WHERE version=3").fetchone()[0]
    ref = plan_api.ref()
    decoded = Counter()
    original_decode = json.JSONDecoder.decode

    def counted(decoder, text, *args, **kwargs):
        decoded[text] += 1
        return original_decode(decoder, text, *args, **kwargs)

    monkeypatch.setattr(json.JSONDecoder, "decode", counted)
    with plan_api.db() as conn:
        conn.execute("BEGIN")
        context = PlanReadContext(conn)
        with context.read_scope():
            entry, _ = context.selected(ref)
            documents = context.history_documents(entry.locator.version)
            assert context.history_documents(entry.locator.version) is documents
            for _ in range(2):
                assert documents.deferred_operation_ids == frozenset({987654})
                assert documents.algorithm == {"mode": "improve"}
                assert documents.operation_effort is None
        conn.rollback()
    # 同一作用域每份文档只解码一次；没读的物料策略不解码。
    assert decoded[deferred_text] == decoded[algorithm_text] == 1
    assert decoded[policy_text] == 0


@pytest.mark.parametrize("variant", ["saved", "duplicate_operation", "unknown_role"])
def test_history_operation_effort_is_admitted_once_into_entries_by_operation_ref(plan_api, variant):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        op_id, operation_ref = conn.execute("SELECT op_id, operation_ref FROM Schedule WHERE version=3").fetchone()
        item = dict(
            OperationEffort(op_id=op_id, batch_id="CAT-B", piece_id=None, source="internal", target_quantity=2,
                            remaining_quantity=2, setup_standard_hours=0.5, processing_standard_hours=3,
                            required_standard_hours=3.5).to_dict(),
            operation_ref=operation_ref,
        )
        items = {"saved": [item], "duplicate_operation": [item, item],
                 "unknown_role": [dict(item, requirement_role="guessed")]}[variant]
        conn.execute(
            "UPDATE ScheduleHistory SET operation_effort_json=? WHERE version=3",
            (canonical_json({"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": items}),),
        )
    with plan_api.db() as conn:
        conn.execute("BEGIN")
        context = PlanReadContext(conn)
        with context.read_scope():
            entry, _ = context.selected(ref)
            documents = context.history_documents(entry.locator.version)
            if variant == "saved":
                assert documents.operation_effort == {operation_ref: item}
            else:
                # 条目损坏与文档读不出是同一种存储损坏。
                with pytest.raises(StoredJsonCorrupt):
                    _ = documents.operation_effort
        conn.rollback()


@pytest.mark.parametrize(
    "column, stored, path",
    [
        ("deferred_operation_ids_json", '["4"]', "/workspace"),
        ("deferred_operation_ids_json", "[true]", "/workspace"),
        ("deferred_operation_ids_json", "[0]", "/workspace"),
        ("deferred_operation_ids_json", "{}", "/workspace"),
        ("algorithm_json", "[]", "/workspace"),
        ("gantt_graph_json", "{", "/gantt-graph"),
    ],
)
def test_corrupt_stored_history_document_is_a_storage_failure(plan_api, column, stored, path):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        conn.execute("UPDATE ScheduleHistory SET " + column + "=? WHERE version=3", (stored,))
    # 整版工作区只用已存的节点数，不解码工序图；工序图在它自己的读取里解码。
    query = {} if path == "/workspace" else {"snapshot_ref": plan_api.read("/" + ref + "/workspace")["meta"]["snapshot_ref"]}
    assert_error(plan_api.get("/" + ref + path, **query), "storage_failure", status=500)


def test_selected_plan_context_calendar_days_and_midnight_point_exclusion(plan_api, monkeypatch):
    d0 = date(2025, 12, 31)
    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 2)
    t_start = datetime(2026, 1, 1, 0, 0)
    t_early = datetime(2026, 1, 1, 10, 0)
    t_end_mid = datetime(2026, 1, 2, 0, 0)
    t_end_day = datetime(2026, 1, 2, 8, 0)
    t_us = datetime(2026, 1, 1, 23, 59, 59, 999999)

    def row(schedule_id, low, high, is_point_event):
        return {"schedule_id": schedule_id, "op_id": schedule_id, "source": "internal", "machine_id": "M1",
                "operator_id": "O1", "is_point_event": is_point_event,
                "start_us": datetime_to_us(low), "end_us": datetime_to_us(high)}

    early_point = row(1, t_early, t_early, 1)
    terminal_point = row(2, t_end_mid, t_end_mid, 1)
    positive_row = row(3, t_start, t_end_mid, 0)

    def ctx(rows, start, end):
        return calendar_context.SelectedPlanContext(
            rows=rows,
            start=start,
            end=end,
            time_scope={"range_start": start.isoformat(), "range_end": end.isoformat()},
        )

    assert ctx([early_point], t_start, t_end_mid).calendar_days == (d0, d1, 2)
    assert ctx([early_point, terminal_point], t_start, t_end_mid).calendar_days == (d0, d2, 3)
    assert ctx([early_point, positive_row], t_start, t_end_mid).calendar_days == (d0, d1, 2)
    assert ctx([early_point], t_start, t_end_day).calendar_days == (d0, d2, 3)
    assert ctx([terminal_point], t_end_mid, t_end_mid).calendar_days == (d1, d2, 2)
    assert ctx([row(4, t_end_day, t_end_day, 1)], t_end_day, t_end_day).calendar_days == (d1, d2, 2)
    assert ctx([], t_start, t_end_mid).calendar_days == (d0, d1, 2)
    assert ctx([row(5, t_us, t_us, 1)], t_us, t_end_mid).calendar_days == (d0, d1, 2)
    assert ctx([row(6, datetime.min, datetime.min, 1)], datetime.min, datetime.min).calendar_days == (date.min, date.min, 1)

    calendar_calls = []
    original_calendar = CalendarFacts.calendar

    def tracked_calendar(self, first_iso, last_iso, operators):
        calendar_calls.append((first_iso, last_iso))
        return original_calendar(self, first_iso, last_iso, operators)

    monkeypatch.setattr(CalendarFacts, "calendar", tracked_calendar)
    ref = plan_api.ref()
    limit_start = datetime(2016, 1, 1, 0, 0)
    limit_end = limit_start + timedelta(days=3659)
    scope = PlanReadScope(ref, limit_start.isoformat(), limit_end.isoformat())
    with plan_api.db() as conn:
        conn.execute("BEGIN")
        context = PlanReadContext(conn)
        with context.read_scope():
            entry, _ = context.selected(ref)
            point_us = datetime_to_us(limit_start + timedelta(hours=8))
            base_row = dict(context.detail_rows(entry)[0], is_point_event=1, start_us=point_us, end_us=point_us)
            resources = context.resource_identities([base_row])
            selected = calendar_context.selected_context(
                scope,
                [base_row],
                {"start": limit_start.isoformat(), "end": limit_end.isoformat()},
            )
            dto, _ = project_plan_calendar(conn, scope=scope, resources=resources, selected=selected, include_windows=False)
        conn.rollback()
    assert dto["state"] == "available"
    assert calendar_calls == [("2015-12-31", "2026-01-06")]
