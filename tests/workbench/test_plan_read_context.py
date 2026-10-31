"""One request captures plan facts once and keeps input bindings strict."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan import calendar_context, queries
from core.services.workbench.plan.point_query import PointPlanCatalogRepository
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from tests._support.gantt_current_js import run_current_js
from tests.workbench.plan_read_support import (  # noqa: F401
    NIGHT_END,
    NIGHT_START,
    add_tasks,
    assert_error,
    plan_read_api,
)


def test_read_context_owns_capture_and_next_request_observes_change(plan_api, monkeypatch):
    with plan_api.db() as conn:
        add_tasks(conn, 1, start="2026-09-10 08:00:00", end="2026-09-10 09:00:00")
    ref, captures, selected_calls = plan_api.ref(), Counter(), []
    storage = WorkbenchPlanCatalogRepository.list_plan_storage_rows
    detail = WorkbenchPlanCatalogRepository.enrich_arrangements
    selected = calendar_context.selected_context

    def storage_rows(repo, **values):
        captures["raw", values["version"]] += 1
        return storage(repo, **values)

    def detail_rows(repo, arrangements, *, captured_machines=None):
        captures["detail", arrangements[0]["version"]] += 1
        return detail(repo, arrangements, captured_machines=captured_machines)

    def selection(*args, **kwargs):
        selected_calls.append(args[1].plan_ref)
        return selected(*args, **kwargs)

    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "list_plan_storage_rows", storage_rows)
    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "enrich_arrangements", detail_rows)
    monkeypatch.setattr(calendar_context, "selected_context", selection)
    scope = PlanReadScope(ref, NIGHT_START, NIGHT_END)
    with plan_api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        conn.execute("BEGIN")
        reader = queries.WorkbenchPlanQueryService(conn)
        statements, changes = [], conn.total_changes
        conn.set_trace_callback(statements.append)
        with reader.read_snapshot():
            context = PlanReadContext(conn, references=reader.references, entities=reader.entities)
            with context.read_scope():
                data, _ = reader.workspace(scope, context=context)
                _, entry, _ = context.selected(ref)
                rows = context.detail_rows(entry)
                tasks, _ = context.projected_tasks(ref, rows, resources=context.resource_identities(rows))
                assert data["task_count"] == 1 and len(rows) == len(tasks) == 2
                assert data["tasks"][0] == tasks[0]
        conn.set_trace_callback(None)
        assert conn.total_changes == changes
        assert captures["raw", 3] == captures["detail", 3] == 1
        assert selected_calls == [ref]
        assert sum("FROM WorkbenchPlanIdentityClock WHERE singleton = 1" in sql for sql in statements) == 1
        assert not any("SELECT schema_version FROM pragma_schema_version" in sql for sql in statements)
        assert sum("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref = '" + ref + "' AND active = 1" in sql
                   for sql in statements) == 1
        assert not any(sql.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}
                       for sql in statements)
    with plan_api.db() as conn:
        conn.execute("UPDATE Schedule SET start_time='2026-09-11T08:00:00',end_time='2026-09-11T09:00:00' WHERE version=3 AND op_id!=1")
        conn.execute("UPDATE Schedule SET start_time='2026-09-11 11:00:00',end_time='2026-09-11 12:00:00' WHERE version=3 AND operator_id='PRIVATE-O1'")
    ordered = plan_api.read("/" + ref + "/workspace")
    assert [t["start"] for t in ordered["data"]["tasks"]] == ["2026-09-11T08:00:00", "2026-09-11T11:00:00"]
    with plan_api.db() as conn:
        conn.execute("UPDATE Schedule SET start_time=?,end_time='2026-09-10T05:30:00' WHERE version=3 AND operator_id='PRIVATE-O1'", (NIGHT_START,))
    changed = plan_api.read("/" + ref + "/workspace", range_start=NIGHT_START, range_end=NIGHT_END)
    assert changed["data"]["tasks"][0]["end"] == "2026-09-10T05:30:00"
    assert run_current_js(r"""
const M = h.runtime.PlanGanttModel, taskFacts = M.prepareTasks(sourceData);
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
        add_tasks(conn, 19999)
        conn.executemany("INSERT INTO Machines(machine_id,name) VALUES (?,?)",
                         [("M" + str(index), "Machine " + str(index)) for index in range(201)])
        conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)",
                         [("O" + str(index), "Operator " + str(index)) for index in range(201)])
        operation_ids = [row[0] for row in conn.execute("SELECT op_id FROM Schedule WHERE version=3 ORDER BY op_id")]
        start = datetime(2026, 1, 1, 8)
        conn.executemany("UPDATE Schedule SET start_time=?,end_time=?,machine_id=?,operator_id=? WHERE version=3 AND op_id=?",
            [((start + timedelta(days=index // 200)).isoformat(),
              (start + timedelta(days=index // 200, hours=1)).isoformat(),
              "M" + str(index % 201), "O" + str(index % 201), operation_id)
             for index, operation_id in enumerate(operation_ids)])
    ref = plan_api.ref()
    with monkeypatch.context() as catalog_read:
        def no_full_capture(*args, **kwargs):
            pytest.fail("Catalog captured complete plan arrangements instead of streaming metadata")

        catalog_read.setattr(PointPlanCatalogRepository, "source_rows", no_full_capture)
        catalog = plan_api.read(collection="history")["data"]["plans"]
    entry = next(row for row in catalog if row["plan_ref"] == ref)
    assert entry["capabilities"]["view"] and entry["capabilities"]["export"]
    assert entry["is_current_official"] and not entry["blocked_reasons"]
    assert_error(plan_api.get("/" + ref + "/workspace"), "query_too_large", status=413)

    plan_api.statements.clear()
    scope = {"range_start": "2026-01-01T00:00:00", "range_end": "2026-01-02T00:00:00"}
    result = plan_api.read("/" + ref + "/workspace", **scope)
    data = result["data"]
    assert data["task_count"] == len(data["tasks"]) == 200 and data["tasks_complete"]
    delivery, = data["projections"]["delivery_risks"]["items"]
    assert delivery["operation_count"] == delivery["scheduled_operation_count"] == 20000
    statements = [sql.upper() for sql in plan_api.statements]
    captures = [sql for sql in statements if 'FROM "SCHEDULE" R' in sql]
    operations = [sql for sql in statements if "BO.STATUS AS OP_STATUS" in sql]
    machines = [sql for sql in statements if sql.startswith("SELECT MACHINE_ID,NAME FROM MACHINES WHERE MACHINE_ID IN (")]
    operators = [sql for sql in statements if sql.startswith("SELECT OPERATOR_ID,NAME FROM OPERATORS WHERE OPERATOR_ID IN (")]
    assert len(captures) == 1 and "LIMIT" not in captures[0]
    assert (len(operations), len(machines), len(operators)) == (50, 1, 1)
    record_property("complete_source_rows", 20000)
    record_property("visible_task_count", data["task_count"])
    record_property("source_capture_queries", len(captures))
    record_property("operation_metadata_queries", len(operations))
    record_property("resource_name_queries", len(machines) + len(operators))

    execution_statements = []
    with plan_api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        conn.set_trace_callback(execution_statements.append)
        reader = queries.WorkbenchPlanQueryService(conn)
        with reader.read_snapshot():
            execution = reader.execution_workspace(PlanReadScope(ref, **scope))
        assert execution["tasks"] == data["tasks"]
        assert execution["task_count"] == 200
        assert sum("BO.STATUS AS OP_STATUS" in sql.upper() for sql in execution_statements) == 1
        record_property("execution_operation_metadata_queries", 1)
        record_property("execution_visible_task_count", execution["task_count"])


def test_plan_endpoints_project_only_requested_slices_and_share_snapshot_state(plan_api, monkeypatch):
    from core.services.workbench.plan import projection

    with plan_api.db() as conn:
        add_tasks(conn, 5000)
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('TAIL-M','Tail machine')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('TAIL-O','Tail operator')")
        operation_ids = [row[0] for row in conn.execute("SELECT op_id FROM Schedule WHERE version=3 ORDER BY op_id")]
        start = datetime(2026, 9, 9, 8)
        conn.executemany(
            "UPDATE Schedule SET start_time=?,end_time=?,machine_id=?,operator_id=? WHERE version=3 AND op_id=?",
            [
                (
                    (start + timedelta(minutes=index)).isoformat(),
                    (start + timedelta(minutes=index + 1)).isoformat(),
                    "TAIL-M" if index == 5000 else "PRIVATE-M1",
                    "TAIL-O" if index == 5000 else "PRIVATE-O1",
                    operation_id,
                )
                for index, operation_id in enumerate(operation_ids)
            ],
        )
    ref = plan_api.ref()
    projected_counts = []
    storage_calls = []
    original_project_tasks = projection.project_tasks
    original_storage_rows = WorkbenchPlanCatalogRepository.list_plan_storage_rows

    def tracked_project_tasks(plan_ref, rows, *args, **kwargs):
        projected_counts.append(len(rows))
        return original_project_tasks(plan_ref, rows, *args, **kwargs)

    def tracked_storage_rows(repo, **values):
        storage_calls.append(values["version"])
        return original_storage_rows(repo, **values)

    monkeypatch.setattr(projection, "project_tasks", tracked_project_tasks)
    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "list_plan_storage_rows", tracked_storage_rows)
    workspace_res = plan_api.read("/" + ref + "/workspace")
    workspace_data = workspace_res["data"]
    token = workspace_res["meta"]["snapshot_ref"]
    assert workspace_data["task_count"] == 5001
    assert len(workspace_data["tasks"]) == 5000 and workspace_data["tasks_complete"] is False
    assert projected_counts == [5000]
    assert storage_calls == [3]
    assert {item["business_code"] for item in workspace_data["resources"]} >= {"TAIL-M", "TAIL-O"}

    projected_counts.clear()
    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in (
            "build_plan_baseline",
            "project_plan_calendar",
            "project_plan_occupancy",
            "read_plan_delivery",
            "project_process_order",
        ):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"tasks_page called {attr}"))
        tasks_p2 = plan_api.read("/" + ref + "/tasks", snapshot_ref=token, page=2, size=5000)
    assert tasks_p2["meta"]["snapshot_ref"] == token
    assert len(tasks_p2["data"]["tasks"]) == 1 and tasks_p2["data"]["tasks_complete"] is False
    assert projected_counts == [1]
    assert storage_calls == [3]

    projected_counts.clear()
    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("project_plan_calendar", "project_plan_occupancy", "read_plan_delivery", "project_process_order"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"baseline_comparison called {attr}"))
        baseline_res = plan_api.read("/" + ref + "/baseline", snapshot_ref=token, page=1, size=5000)
    assert baseline_res["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == [3]

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "project_plan_calendar", "project_plan_occupancy", "read_plan_delivery"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"gantt_graph called {attr}"))
        graph_res = plan_api.read("/" + ref + "/gantt-graph", snapshot_ref=token)
    assert graph_res["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == [3]

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "read_plan_delivery", "project_process_order"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"capacity_projections called {attr}"))
        cap_res = plan_api.read("/" + ref + "/capacity", snapshot_ref=token)
    assert cap_res["meta"]["snapshot_ref"] == token
    assert projected_counts == []
    assert storage_calls == [3]

    storage_calls.clear()
    with monkeypatch.context() as patch:
        for attr in ("build_plan_baseline", "project_plan_calendar", "project_plan_occupancy", "project_process_order"):
            patch.setattr(queries, attr, lambda *a, **kw: pytest.fail(f"export_workspace called {attr}"))
        export_res = plan_api.get("/" + ref + "/export", snapshot_ref=token, format="csv")
    assert export_res.status_code == 200
    assert export_res.headers["X-Workbench-Snapshot-Ref"] == token
    assert export_res.headers["X-Workbench-Row-Count"] == "5001"
    assert projected_counts == [5001]
    assert storage_calls == [3]

    storage_calls.clear()
    with plan_api.db() as conn:
        conn.execute("UPDATE Machines SET remark='Stale machine fact' WHERE machine_id='PRIVATE-M1'")
    assert_error(plan_api.get("/" + ref + "/tasks", snapshot_ref=token, page=2, size=5000), "snapshot_stale", status=409)
    assert storage_calls == []
