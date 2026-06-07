"""回归测试：资源派工任务 id 的哈希契约——非法 Unicode 触发 UnicodeEncodeError；内部 schedule_id/op_id 等隐藏身份不泄漏进公开 payload 与可读前缀；任务 id 在不同可见区间、operator/machine 视图间稳定，但能按资源对区分同工序同时段行；可读前缀剔除分隔符并支撑依赖链。"""

from __future__ import annotations

import json

import pytest

from core.services.scheduler.resource_dispatch_range import resolve_dispatch_range
from core.services.scheduler.resource_dispatch_rows import build_dispatch_detail_rows, build_dispatch_tasks
from core.services.scheduler.resource_dispatch_support import build_single_scope_payload, build_team_scope_payload
from core.services.scheduler.resource_dispatch_task_ids import row_identity


def test_resource_dispatch_task_id_rejects_invalid_unicode_in_hash_source() -> None:
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
        build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=[row])


def test_resource_dispatch_task_id_keeps_hidden_identity_in_hash() -> None:
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
        rows=[dict(base_row, schedule_id=1), dict(base_row, schedule_id=2)],
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
        outcome = build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=[row])
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
        outcome = build_dispatch_tasks(scope_id="OP001", dr=dispatch_range, rows=[row])
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

    operator_rows = build_dispatch_detail_rows(
        scope_type="operator",
        scope_id="OP001",
        scope_name="张三",
        rows=[dict(base_row, operator_name="张三", machine_name="设备1")],
        overdue_set=set(),
    ).value
    machine_rows = build_dispatch_detail_rows(
        scope_type="machine",
        scope_id="MC001",
        scope_name="设备1",
        rows=[dict(base_row, operator_name="张三", machine_name="设备1")],
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
        rows=[
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
        ],
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
        rows=[
            dict(base_row, operator_id="OP001", operator_name="张三", machine_id="MC001", machine_name="设备1"),
            dict(base_row, operator_id="OP002", operator_name="李四", machine_id="MC002", machine_name="设备2"),
        ],
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
        rows=[
            dict(base_row, operator_id="OP001", operator_name="张三", machine_id="MC001", machine_name="设备1"),
            dict(base_row, operator_id="OP002", operator_name="李四", machine_id="MC002", machine_name="设备2"),
        ],
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
        rows=[row],
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
        rows=[
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
        ],
    )
    first, second = outcome.value

    assert "," not in first["id"]
    assert "/" not in first["id"]
    assert second["dependencies"] == first["id"]
