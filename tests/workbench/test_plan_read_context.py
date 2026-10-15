"""One request captures plan facts once and keeps input bindings strict."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan import calendar_context, queries
from core.services.workbench.plan.delivery import read_plan_delivery
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
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
        captures["raw", values["version"], values["source_table"]] += 1
        return storage(repo, **values)

    def detail_rows(repo, arrangements, *, version, captured_machines=None):
        captures["detail", version] += 1
        return detail(repo, arrangements, version=version, captured_machines=captured_machines)

    def selection(*args, **kwargs):
        selected_calls.append(args[2].plan_ref)
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
                tasks, _, _, _ = context.projected_tasks(ref, entry)
                assert data["task_count"] == 1 and len(rows) == len(tasks) == 2
                assert data["tasks"][0] == tasks[0]
                for changed in (dict(rows[0], op_id=rows[1]["op_id"]), dict(rows[0], version=2)):
                    with pytest.raises(WorkbenchPlanReferenceError) as rejected:
                        context.task_refs(ref, [changed])
                    assert rejected.value.code == "task_binding_invalid"
        conn.set_trace_callback(None)
        assert conn.total_changes == changes
        assert captures["raw", 3, "schedule"] == captures["detail", 3] == 1
        assert selected_calls == [ref]
        assert sum("FROM WorkbenchPlanIdentityClock WHERE singleton = 1" in sql for sql in statements) == 1
        assert sum("SELECT schema_version FROM pragma_schema_version" in sql for sql in statements) == 1
        assert sum("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref = '" + ref + "' AND active = 1" in sql
                   for sql in statements) == 1
        assert not any(sql.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}
                       for sql in statements)
    with plan_api.db() as conn:
        conn.execute("UPDATE Schedule SET end_time='2026-09-10T05:30:00' WHERE version=3 AND operator_id='PRIVATE-O1'")
    changed = plan_api.read("/" + ref + "/workspace", range_start=NIGHT_START, range_end=NIGHT_END)
    assert changed["data"]["tasks"][0]["end"] == "2026-09-10T05:30:00"
    with plan_api.db() as conn:
        conn.execute("UPDATE Schedule SET end_time=start_time WHERE version=3 AND operator_id='PRIVATE-O1'")
    with plan_api.db() as conn:
        conn.execute("PRAGMA query_only=1")
        conn.execute("BEGIN")
        public, facts = read_plan_delivery(conn, scope=PlanReadScope(ref), identity=entry.plan_identity)
        assert public["items"][0]["completeness"] == "unknown"
        assert facts["tasks"][0]["point_evidence_issue"] == "point_evidence_unproven"


def test_20k_saved_plan_is_selectable_and_one_day_reads_200_tasks_from_one_capture(plan_api, record_property):
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
