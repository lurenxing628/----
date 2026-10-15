"""One request captures plan facts once and keeps input bindings strict."""

from collections import Counter

import pytest

from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan import calendar_context, queries
from core.services.workbench.plan.delivery import read_plan_delivery
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from tests.workbench.plan_read_support import NIGHT_END, NIGHT_START, add_tasks, plan_read_api  # noqa: F401


def test_read_context_owns_capture_and_next_request_observes_change(plan_api, monkeypatch):
    with plan_api.db() as conn:
        add_tasks(conn, 1, start="2026-09-10 08:00:00", end="2026-09-10 09:00:00")
    ref, captures, selected_calls = plan_api.ref(), Counter(), []
    storage = WorkbenchPlanCatalogRepository.list_plan_storage_rows_bounded
    detail = WorkbenchPlanCatalogRepository.list_detail_rows_bounded
    selected = calendar_context.selected_context

    def storage_rows(repo, **values):
        captures["raw", values["version"], values["source_table"]] += 1
        return storage(repo, **values)

    def detail_rows(repo, **values):
        captures["detail", values["version"], values["source_table"]] += 1
        return detail(repo, **values)

    def selection(*args, **kwargs):
        selected_calls.append(args[2].plan_ref)
        return selected(*args, **kwargs)

    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "list_plan_storage_rows_bounded", storage_rows)
    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "list_detail_rows_bounded", detail_rows)
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
        assert captures["raw", 3, "schedule"] == captures["detail", 3, "schedule"] == 1
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
