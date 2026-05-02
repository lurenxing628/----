from __future__ import annotations

from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)


def test_resource_dispatch_context_decorates_filters_and_options_without_mutation() -> None:
    context = {
        "filters": {
            "scope_type": "team",
            "scope_id": "TEAM-01",
            "scope_name": "装配一组",
            "team_axis": "machine",
            "period_preset": "week",
        },
        "operator_options": [{"id": "OP001", "name": "张三"}],
        "machine_options": [{"id": "MC001", "name": "数控车床1"}],
        "team_options": [{"id": "TEAM-01", "name": "装配一组"}],
    }

    out = decorate_resource_dispatch_context(context)

    filters = out["filters"]
    assert filters["scope_type_label"] == "班组"
    assert filters["team_axis_label"] == "设备轴"
    assert filters["period_preset_label"] == "按周"
    assert filters["scope_label"] == "TEAM-01 装配一组"
    assert out["operator_options"][0]["label"] == "OP001 张三"
    assert out["machine_options"][0]["label"] == "MC001 数控车床1"
    assert out["team_options"][0]["label"] == "TEAM-01 装配一组"
    assert "scope_type_label" not in context["filters"]
    assert "label" not in context["operator_options"][0]


def test_resource_dispatch_payload_decorates_detail_tasks_and_calendar_text() -> None:
    payload = {
        "filters": {
            "scope_type": "operator",
            "scope_id": "OP001",
            "scope_name": "张三",
            "team_axis": "operator",
            "period_preset": "custom",
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "version": 7,
        },
        "detail_rows": [
            {
                "scope_type": "operator",
                "scope_id": "OP001",
                "scope_name": "张三",
                "current_resource_id": "OP001",
                "current_resource_name": "张三",
                "current_team_id": "TEAM-OP",
                "counterpart_resource_id": "MC001",
                "counterpart_resource_name": "数控车床1",
                "counterpart_team_id": "TEAM-MC",
                "machine_id": "MC001",
                "machine_name": "数控车床1",
                "operator_id": "OP001",
                "operator_name": "张三",
                "op_code": "OP10",
                "part_no": "P001",
            }
        ],
        "tasks": [
            {
                "id": "schedule_1",
                "name": "OP10",
                "meta": {
                    "scope_type": "operator",
                    "scope_id": "OP001",
                    "scope_name": "张三",
                    "current_resource_id": "OP001",
                    "current_resource_name": "张三",
                    "current_team_id": "TEAM-OP",
                    "counterpart_resource_id": "MC001",
                    "counterpart_resource_name": "数控车床1",
                    "counterpart_team_id": "TEAM-MC",
                    "machine_id": "MC001",
                    "machine_name": "数控车床1",
                    "operator_id": "OP001",
                    "operator_name": "张三",
                    "op_code": "OP10",
                    "part_no": "P001",
                },
            }
        ],
        "calendar_rows": [
            {
                "scope_type": "operator",
                "scope_id": "OP001",
                "scope_name": "张三",
                "current_resource_id": "OP001",
                "current_resource_name": "张三",
                "operator_id": "OP001",
                "operator_name": "张三",
                "cells": [
                    {
                        "date": "2026-03-02",
                        "items": [
                            {
                                "start": "2026-03-02 08:00:00",
                                "end": "2026-03-02 10:00:00",
                                "scope_type": "operator",
                                "machine_id": "MC001",
                                "machine_name": "数控车床1",
                                "operator_id": "OP001",
                                "operator_name": "张三",
                                "op_code": "OP10",
                                "part_no": "P001",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    out = decorate_resource_dispatch_payload(payload)
    row = out["detail_rows"][0]
    task = out["tasks"][0]
    calendar_row = out["calendar_rows"][0]
    calendar_item = calendar_row["cells"][0]["items"][0]

    assert row["current_resource_label"] == "OP001 张三"
    assert row["counterpart_resource_label"] == "MC001 数控车床1"
    assert row["team_relation_label"] == "跨班组"
    assert task["name"] == "OP10 MC001 数控车床1"
    assert task["meta"]["counterpart_resource_label"] == "MC001 数控车床1"
    assert calendar_row["scope_label"] == "OP001 张三"
    assert calendar_item["counterpart_resource_label"] == "MC001 数控车床1"
    assert calendar_item["text"] == "08:00-10:00 OP10 MC001 数控车床1 P001"
    assert calendar_row["cells"][0]["text"] == "08:00-10:00 OP10 MC001 数控车床1 P001"


def test_resource_dispatch_payload_labels_external_and_unassigned_resources() -> None:
    payload = {
        "detail_rows": [
            {
                "scope_type": "operator",
                "scope_id": "OP001",
                "scope_name": "张三",
                "operator_id": "OP001",
                "operator_name": "张三",
                "supplier_name": "外协供应商",
            },
            {
                "scope_type": "machine",
                "scope_id": "MC001",
                "scope_name": "数控车床1",
            },
        ]
    }

    out = decorate_resource_dispatch_payload(payload)

    assert out["detail_rows"][0]["counterpart_resource_label"] == "外协供应商：外协供应商"
    assert out["detail_rows"][1]["counterpart_resource_label"] == "外协未分配"


def test_resource_dispatch_payload_decorates_task_without_meta() -> None:
    payload = {
        "filters": {
            "scope_type": "operator",
            "scope_id": "O1",
            "scope_name": "张三",
            "team_axis": "machine",
            "period_preset": "week",
        },
        "tasks": [
            {"id": "task-1"},
            {"id": "task-2", "meta": "bad-meta"},
            {"id": "task-3", "meta": ["bad-meta"]},
        ],
    }

    out = decorate_resource_dispatch_payload(payload)

    assert out["tasks"][0]["name"] == "task-1"
    assert out["tasks"][1]["name"] == "task-2"
    assert out["tasks"][2]["name"] == "task-3"


def test_resource_dispatch_counterpart_label_uses_counterpart_resource_name_fallback() -> None:
    payload = {
        "detail_rows": [
            {
                "scope_type": "operator",
                "scope_id": "OP001",
                "scope_name": "张三",
                "counterpart_resource_id": "MC001",
                "counterpart_resource_name": "设备一",
            },
            {
                "scope_type": "machine",
                "scope_id": "MC001",
                "scope_name": "设备一",
                "counterpart_resource_id": "OP001",
                "counterpart_resource_name": "张三",
            },
        ]
    }

    out = decorate_resource_dispatch_payload(payload)

    assert out["detail_rows"][0]["counterpart_resource_label"] == "MC001 设备一"
    assert out["detail_rows"][1]["counterpart_resource_label"] == "OP001 张三"


def test_resource_dispatch_export_filename_uses_decorated_filter_labels() -> None:
    payload = decorate_resource_dispatch_payload(
        {
            "filters": {
                "scope_type": "operator",
                "scope_id": "OP001",
                "scope_name": "张三",
                "team_axis": "operator",
                "period_preset": "week",
                "start_date": "2026-03-02",
                "end_date": "2026-03-08",
                "version": 7,
            }
        }
    )

    assert build_resource_dispatch_filename(payload) == "资源排班_人员_OP001_2026-03-02_2026-03-08_v7.xlsx"


def test_resource_dispatch_export_filename_uses_team_axis_label() -> None:
    payload = decorate_resource_dispatch_payload(
        {
            "filters": {
                "scope_type": "team",
                "scope_id": "TEAM-01",
                "scope_name": "装配一组",
                "team_axis": "operator",
                "period_preset": "week",
                "start_date": "2026-05-01",
                "end_date": "2026-05-07",
                "version": 9,
            }
        }
    )

    filename = build_resource_dispatch_filename(payload)

    assert filename == "资源排班_班组_TEAM-01_人员轴_2026-05-01_2026-05-07_v9.xlsx"
    assert "operator" not in filename
