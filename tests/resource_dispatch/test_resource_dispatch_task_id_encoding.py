"""资源派工任务编号来自完整计划；公开编号隐藏内部定位键，并在范围、资源视图和依赖链中保持一致。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.common.plan_task_identity import assign_task_ids, row_identity
from core.services.scheduler.resource_dispatch.range import resolve_dispatch_range
from core.services.scheduler.resource_dispatch.rows import build_dispatch_detail_rows, build_dispatch_tasks
from core.services.scheduler.resource_dispatch.support import build_single_scope_payload, build_team_scope_payload
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.operation_execution.operation_execution_state_revision_support import _connect, _seed_plan
from tests.workbench.plan_catalog_support import candidate, selection

_PLAN_IDENTITY = {"version": 1, "effective_plan_role": "adopted", "source_table": "schedule",
                  "scenario_id": None, "plan_ref": None}


def _full_plan_rows(rows):
    return assign_task_ids(rows, plan_identity=_PLAN_IDENTITY)


def test_resource_dispatch_task_id_rejects_invalid_unicode_in_public_source() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    row = {
        "op_code": "OP\ud80010",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "current_resource_id": "OP001",
        "counterpart_resource_id": "MC001",
    }

    with pytest.raises(UnicodeEncodeError):
        build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=_full_plan_rows([row]))


def test_resource_dispatch_task_id_distinguishes_source_rows_without_exposing_internal_ids() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    base_row = {
        "op_code": "OP10",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "current_resource_id": "OP001",
        "counterpart_resource_id": "MC001",
    }

    outcome = build_dispatch_tasks(
        scope_id="OP001",
        dr=dispatch_range,
        rows=_full_plan_rows([dict(base_row, schedule_id=1), dict(base_row, schedule_id=2)]),
    )
    ids = [task["id"] for task in outcome.value]

    assert len(set(ids)) == 2
    assert all("schedule_" not in task_id and "op_" not in task_id for task_id in ids)


def test_resource_dispatch_task_id_is_stable_across_visible_ranges() -> None:
    row = {
        "schedule_id": 123,
        "op_id": 456,
        "op_code": "OP10",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-06 10:00:00",
        "operator_id": "OP001",
        "operator_name": "张三",
        "machine_id": "MC001",
        "machine_name": "设备1",
    }

    source_rows = _full_plan_rows([row])
    ids = []
    visible_starts = []
    for start_date, end_date in (
        ("2026-05-04", "2026-05-04"),
        ("2026-05-05", "2026-05-05"),
        ("2026-05-04", "2026-05-06"),
    ):
        dispatch_range = resolve_dispatch_range(
            period_preset="custom",
            start_date=start_date,
            end_date=end_date,
        )
        outcome = build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=source_rows)
        assert len(outcome.value) == 1
        ids.append(outcome.value[0]["id"])
        visible_starts.append(outcome.value[0]["start"])

    assert len(set(ids)) == 1
    assert len(set(visible_starts)) > 1
    assert "schedule_123" not in ids[0]
    assert "op_456" not in ids[0]


def test_resource_dispatch_task_id_is_stable_across_ranges_without_schedule_id() -> None:
    internal_op_id = "INTERNAL-OP-ID-987654"
    row = {
        "op_id": internal_op_id,
        "op_code": "",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-06 10:00:00",
        "operator_id": "OP001",
        "machine_id": "MC001",
        "current_resource_id": "OP001",
        "counterpart_resource_id": "MC001",
    }

    source_rows = _full_plan_rows([row])
    ids = []
    for start_date, end_date in (
        ("2026-05-04", "2026-05-04"),
        ("2026-05-05", "2026-05-05"),
        ("2026-05-04", "2026-05-06"),
    ):
        dispatch_range = resolve_dispatch_range(
            period_preset="custom",
            start_date=start_date,
            end_date=end_date,
        )
        outcome = build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=source_rows)
        assert len(outcome.value) == 1
        ids.append(outcome.value[0]["id"])

    assert len(set(ids)) == 1
    assert internal_op_id not in ids[0]
    assert "op_INTERNAL" not in ids[0]


def test_resource_dispatch_task_id_is_stable_across_operator_and_machine_views() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    base_row = {
        "op_id": "INTERNAL-OP-ID-987654",
        "op_code": "OP10",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "operator_id": "OP001",
        "machine_id": "MC001",
    }

    source_rows = _full_plan_rows([dict(base_row, operator_name="张三", machine_name="设备1")])
    operator_rows = build_dispatch_detail_rows(
        scope_type="operator",
        scope_id="OP001",
        scope_name="张三",
        rows=source_rows,
        overdue_set=set(),
    ).value
    machine_rows = build_dispatch_detail_rows(
        scope_type="machine",
        scope_id="MC001",
        scope_name="设备1",
        rows=source_rows,
        overdue_set=set(),
    ).value
    operator_task = build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=operator_rows).value[0]
    machine_task = build_dispatch_tasks(scope_id="MC001", dr=dispatch_range, rows=machine_rows).value[0]

    assert operator_task["id"] == machine_task["id"]
    assert "INTERNAL-OP-ID" not in operator_task["id"]
    assert "op_INTERNAL" not in operator_task["id"]


def test_resource_dispatch_missing_op_code_keeps_internal_op_id_out_of_public_payload() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    internal_op_id = "INTERNAL-OP-ID-987654"

    payload = build_single_scope_payload(
        normalized_scope_type="operator",
        selected_scope_id="OP001",
        selected_scope_name="张三",
        dr=dispatch_range,
        rows=_full_plan_rows([
            {
                "op_id": internal_op_id,
                "op_code": "",
                "batch_id": "B001",
                "piece_id": "P1",
                "part_no": "P001",
                "seq": 10,
                "start_time": "2026-05-04 08:00:00",
                "end_time": "2026-05-04 10:00:00",
                "operator_id": "OP001",
                "operator_name": "张三",
                "machine_id": "MC001",
                "machine_name": "设备1",
            }
        ]),
        overdue_set=set(),
    )

    public_json = json.dumps(payload, ensure_ascii=False)
    task = payload["tasks"][0]
    calendar_item = payload["calendar_rows"][0]["cells"][0]["items"][0]

    assert internal_op_id not in public_json
    assert "op_INTERNAL" not in public_json
    assert payload["detail_rows"][0]["op_code"] == ""
    assert task["id"].startswith("task_B001_")
    assert task["name"] == "B001 工序10"
    assert calendar_item["text"] == "08:00-10:00 B001 工序10 P001"


def test_resource_dispatch_row_identity_distinguishes_same_op_time_different_resources_without_schedule_id() -> None:
    base_row = {
        "op_id": "INTERNAL-OP-ID-987654",
        "op_code": "",
        "batch_id": "B001",
        "piece_id": "P1",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
    }

    first = row_identity(dict(base_row, operator_id="OP001", machine_id="MC001"))
    second = row_identity(dict(base_row, operator_id="OP002", machine_id="MC002"))
    machine_changed = row_identity(dict(base_row, operator_id="OP001", machine_id="MC002"))
    operator_changed = row_identity(dict(base_row, operator_id="OP002", machine_id="MC001"))

    assert len({first, second, machine_changed, operator_changed}) == 4


def test_resource_dispatch_summary_counts_same_op_time_different_resources_without_schedule_id() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    base_row = {
        "op_id": "INTERNAL-OP-ID-987654",
        "op_code": "",
        "batch_id": "B001",
        "piece_id": "P1",
        "part_no": "P001",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "source": "internal",
    }

    payload = build_single_scope_payload(
        normalized_scope_type="operator",
        selected_scope_id="",
        selected_scope_name="",
        dr=dispatch_range,
        rows=_full_plan_rows([
            dict(base_row, operator_id="OP001", operator_name="张三", machine_id="MC001", machine_name="设备1"),
            dict(base_row, operator_id="OP002", operator_name="李四", machine_id="MC002", machine_name="设备2"),
        ]),
        overdue_set=set(),
    )

    assert len(payload["detail_rows"]) == 2
    assert len(payload["tasks"]) == 2
    assert len({task["id"] for task in payload["tasks"]}) == 2
    assert payload["summary"]["total_tasks"] == 2
    assert payload["summary"]["total_hours"] == 4.0


def test_resource_dispatch_team_summary_counts_same_op_time_different_cross_team_resources_without_schedule_id() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    base_row = {
        "op_id": "INTERNAL-OP-ID-987654",
        "op_code": "",
        "batch_id": "B001",
        "piece_id": "P1",
        "part_no": "P001",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "source": "internal",
        "operator_team_id": "TEAM-A",
        "operator_team_name": "一组",
        "machine_team_id": "TEAM-B",
        "machine_team_name": "二组",
    }

    payload = build_team_scope_payload(
        selected_scope_id="TEAM-A",
        selected_scope_name="一组",
        normalized_team_axis="operator",
        dr=dispatch_range,
        rows=_full_plan_rows([
            dict(base_row, operator_id="OP001", operator_name="张三", machine_id="MC001", machine_name="设备1"),
            dict(base_row, operator_id="OP002", operator_name="李四", machine_id="MC002", machine_name="设备2"),
        ]),
        overdue_set=set(),
    )

    assert len(payload["detail_rows"]) == 2
    assert len(payload["tasks"]) == 2
    assert len({task["id"] for task in payload["tasks"]}) == 2
    assert len(payload["cross_team_rows"]) == 2
    assert payload["summary"]["total_tasks"] == 2
    assert payload["summary"]["operator_task_count"] == 2
    assert payload["summary"]["cross_team_sheet_count"] == 2


def test_resource_dispatch_team_summary_deduplicates_same_task_on_operator_and_machine_axes_without_schedule_id() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )
    row = {
        "op_id": "INTERNAL-OP-ID-987654",
        "op_code": "",
        "batch_id": "B001",
        "piece_id": "P1",
        "part_no": "P001",
        "seq": 10,
        "start_time": "2026-05-04 08:00:00",
        "end_time": "2026-05-04 10:00:00",
        "source": "internal",
        "operator_id": "OP001",
        "operator_name": "张三",
        "machine_id": "MC001",
        "machine_name": "设备1",
        "operator_team_id": "TEAM-A",
        "operator_team_name": "一组",
        "machine_team_id": "TEAM-A",
        "machine_team_name": "一组",
    }

    payload = build_team_scope_payload(
        selected_scope_id="TEAM-A",
        selected_scope_name="一组",
        normalized_team_axis="operator",
        dr=dispatch_range,
        rows=_full_plan_rows([row]),
        overdue_set=set(),
    )

    assert len(payload["operator_rows"]) == 1
    assert len(payload["machine_rows"]) == 1
    assert payload["summary"]["total_tasks"] == 1
    assert payload["summary"]["operator_task_count"] == 1
    assert payload["summary"]["machine_task_count"] == 1


def test_resource_dispatch_task_id_readable_prefix_is_dependency_safe() -> None:
    dispatch_range = resolve_dispatch_range(
        period_preset="custom",
        start_date="2026-05-04",
        end_date="2026-05-04",
    )

    outcome = build_dispatch_tasks(
        scope_id="OP001",
        dr=dispatch_range,
        rows=_full_plan_rows([
            {
                "schedule_id": 1,
                "op_code": "OP,10 / 首件",
                "batch_id": "B001",
                "piece_id": "P1",
                "seq": 10,
                "start_time": "2026-05-04 08:00:00",
                "end_time": "2026-05-04 10:00:00",
                "current_resource_id": "OP001",
                "counterpart_resource_id": "MC001",
            },
            {
                "schedule_id": 2,
                "op_code": "OP20",
                "batch_id": "B001",
                "piece_id": "P1",
                "seq": 20,
                "start_time": "2026-05-04 10:00:00",
                "end_time": "2026-05-04 12:00:00",
                "current_resource_id": "OP001",
                "counterpart_resource_id": "MC001",
            },
        ]),
    )
    first, second = outcome.value

    assert "," not in first["id"]
    assert "/" not in first["id"]
    assert second["dependencies"] == first["id"]


def test_complete_plan_ids_survive_cold_reordering_filters_and_existing_references(tmp_path: Path) -> None:
    base = {"version": 1, "op_code": "", "piece_id": "P1", "seq": 10,
            "start_time": "2026-05-04 08:00:00", "end_time": "2026-05-04 10:00:00",
            "operator_id": "OP001", "operator_name": "张三"}
    permanent_ref = "a" * 48
    full_source = [
        dict(base, schedule_id=991, op_id=999991, batch_id="B001", machine_id="MC001"),
        dict(base, schedule_id=701, op_id=999701, batch_id="B002", machine_id="MC002",
             task_id="task_original_issued", task_ref="b" * 48),
        dict(base, schedule_id=801, op_id=999801, batch_id="B003", machine_id="MC002",
             public_task_id="task_original_public"),
        dict(base, schedule_id=901, op_id=999901, batch_id="B004", machine_id="MC001", task_ref=permanent_ref),
    ]
    assigned = _full_plan_rows(full_source)
    expected = {row["schedule_id"]: row["task_id"] for row in assigned}
    cold = _full_plan_rows([dict(row) for row in reversed(full_source)])
    assert {row["schedule_id"]: row["task_id"] for row in cold} == expected
    assert assigned[1]["task_id"] == "task_original_issued"
    assert assigned[1]["task_ref"] == full_source[1]["task_ref"]
    assert assigned[2]["task_id"] == full_source[2]["public_task_id"]
    assert assigned[3]["task_id"] == "task_" + permanent_ref
    assert assigned[3]["task_ref"] == permanent_ref
    assert "task_id" not in full_source[0]

    class CompletePlanRepository:
        def __init__(self, rows):
            self.rows, self.full_reads = rows, 0

        def list_detail_rows_all(self, **locator):
            assert locator == {"version": 1, "source_table": "schedule", "candidate_id": None, "scenario_id": None}
            self.full_reads += 1
            return [dict(row) for row in self.rows]

        def list_dispatch_rows(self, **query):
            assert query["scope_type"] == "machine"
            return [dict(row) for row in self.rows if row["machine_id"] == query["scope_id"]]

    dr = resolve_dispatch_range(period_preset="custom", start_date="2026-05-04", end_date="2026-05-04")
    for source_rows in (full_source, [dict(row) for row in reversed(full_source)]):
        repo = CompletePlanRepository(source_rows)
        query = SchedulePlanQueryService(None, repo=repo)
        selected = query.list_plan_dispatch_rows_for_resolution(
            version=1, source_table="schedule", candidate_id=None, start_time=dr.start_time, end_time=dr.end_time,
            scope_type="machine", scope_id="MC001")
        assert {row["schedule_id"]: row["task_id"] for row in selected} == {
            key: expected[key] for key in (991, 901)}
        detail_rows = build_dispatch_detail_rows(
            scope_type="machine", scope_id="MC001", scope_name="设备1", rows=selected, overdue_set=set()).value
        rendered = build_dispatch_tasks(scope_id="MC001", dr=dr, rows=detail_rows).value
        assert {row["id"] for row in rendered} == {expected[991], expected[901]}
        assert query.task_id_for_row(selected[0], version=1, source_table="schedule") == expected[selected[0]["schedule_id"]]
        assert repo.full_reads == 1

    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        candidate(conn, 1, "adopted", source="schedule")
        shared = candidate(conn, 1, "baseline_best", op_id=10)
        selection(conn, 1, "critical_best", shared, source="candidate_rows")
        conn.commit()
        scope = {"version": 1, "source_table": "candidate_rows", "candidate_id": shared}
        source_rows = SchedulePlanQueryRepository(conn).list_detail_rows_all(**scope)
        references = WorkbenchPlanIdentityRepository(conn)
        roles = ("baseline_best", "critical_best")
        plans = {role: references.get_plan_ref(WorkbenchPlanLocator(1, role)) for role in roles}
        expected_ids = {
            role: {row_id: "task_" + task_ref for row_id, task_ref in
                   references.get_task_refs(plans[role], source_rows).items()} for role in roles}
        assert plans[roles[0]] != plans[roles[1]]
        assert expected_ids[roles[0]] != expected_ids[roles[1]]
        modern_query = SchedulePlanQueryService(conn)
        for role in roles:
            rows = modern_query.public_task_rows_for_resolution(**scope, effective_plan_role=role)
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
        with pytest.raises(ValueError, match="多个角色"):
            modern_query.public_task_rows_for_resolution(**scope)
        for role in roles:
            rows = modern_query.public_task_rows_for_resolution(**scope, plan_ref=plans[role])
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
            assert (modern_query.task_id_for_row(source_rows[0], **scope, plan_ref=plans[role])
                    == expected_ids[role][source_rows[0]["schedule_id"]])
            rows = modern_query.list_plan_detail_rows_all(version=1, role=role)
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
        with pytest.raises(ValueError, match="角色"):
            modern_query.public_task_rows_for_resolution(
                **scope, effective_plan_role="critical_best", plan_ref=plans["baseline_best"])
    finally:
        conn.close()
