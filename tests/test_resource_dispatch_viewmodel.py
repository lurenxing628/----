from __future__ import annotations

import json
from typing import Any, Set

from web.viewmodels.scheduler_resource_dispatch import (
    build_resource_dispatch_filename,
    decorate_resource_dispatch_context,
    decorate_resource_dispatch_payload,
)

FORBIDDEN_PLAN_ROLE_OPTION_KEYS = (
    "source_table",
    "candidate_id",
    "selection_candidate_id",
    "resolved_candidate_id",
    "candidate_key",
    "candidate_kind",
    "candidate_status",
    "detail_saved",
    "scenario_id",
)

FORBIDDEN_PUBLIC_FILTER_KEYS = FORBIDDEN_PLAN_ROLE_OPTION_KEYS + (
    "plan_role",
    "requested_plan_role",
    "effective_plan_role",
    "plan_role_status",
)

FORBIDDEN_PUBLIC_ROW_KEYS = {"schedule_id", "op_id", "_row_identity"}


def _json_keys(value: Any) -> Set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_json_keys(child))
        return keys
    if isinstance(value, list):
        keys: Set[str] = set()
        for child in value:
            keys.update(_json_keys(child))
        return keys
    return set()


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


def test_resource_dispatch_plan_role_options_hide_internal_fields_from_public_json() -> None:
    payload = {
        "filters": {
            "scope_type": "operator",
            "scope_id": "OP001",
            "scope_name": "张三",
            "team_axis": "operator",
            "period_preset": "week",
            "version": 7,
            "plan_role": "baseline_best",
            "requested_plan_role": "baseline_best",
            "effective_plan_role": "baseline_best",
            "plan_role_status": "resolved_comparison",
            "source_table": "scheduler_candidate_selection",
            "candidate_id": 12,
            "selection_candidate_id": 13,
            "resolved_candidate_id": 14,
            "candidate_key": "internal-key",
            "candidate_kind": "baseline",
            "candidate_status": "ready",
            "detail_saved": True,
            "scenario_id": "scenario-001",
        },
        "plan_role_options": [
            {
                "role": "baseline_best",
                "label": "原算法代表方案",
                "is_comparison": True,
                "source_table": "scheduler_candidate_selection",
                "candidate_id": 12,
                "selection_candidate_id": 13,
                "resolved_candidate_id": 14,
                "candidate_key": "internal-key",
                "candidate_kind": "baseline",
                "candidate_status": "ready",
                "detail_saved": True,
                "scenario_id": "scenario-001",
            }
        ]
    }
    expected = [{"role": "baseline_best", "label": "原算法代表方案", "is_comparison": True}]

    payload_out = decorate_resource_dispatch_payload(payload)
    context_out = decorate_resource_dispatch_context(payload)

    assert payload_out["plan_role_options"] == expected
    assert context_out["plan_role_options"] == expected
    assert payload_out["filters"]["scope_type"] == "operator"
    assert payload_out["filters"]["scope_type_label"] == "人员"
    assert context_out["client_filters"]["scope_type"] == "operator"
    assert context_out["client_filters"]["scope_type_label"] == "人员"
    for key in FORBIDDEN_PUBLIC_FILTER_KEYS:
        assert key not in payload_out["filters"]
        assert key not in context_out["client_filters"]
    public_json = json.dumps(
        {
            "payload": payload_out,
            "client_filters": context_out["client_filters"],
            "plan_role_options": context_out["plan_role_options"],
        },
        ensure_ascii=False,
    )
    public_keys = _json_keys(json.loads(public_json))
    for key in FORBIDDEN_PUBLIC_FILTER_KEYS:
        assert key not in public_keys


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
                                "time_label": "08:00-10:00",
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


def test_resource_dispatch_payload_keeps_calendar_day_segment_label() -> None:
    payload = {
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
                        "date": "2026-03-03",
                        "items": [
                            {
                                "start": "2026-03-03 00:00:00",
                                "end": "2026-03-04 00:00:00",
                                "time_label": "全天",
                                "scope_type": "operator",
                                "machine_id": "MC001",
                                "machine_name": "数控车床1",
                                "operator_id": "OP001",
                                "operator_name": "张三",
                                "op_code": "OP10",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    out = decorate_resource_dispatch_payload(payload)

    item_text = out["calendar_rows"][0]["cells"][0]["items"][0]["text"]
    assert item_text == "全天 OP10 MC001 数控车床1"
    assert "00:00-00:00" not in item_text


def test_resource_dispatch_payload_keeps_legacy_calendar_text_when_time_label_missing() -> None:
    payload = {
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
                        "date": "2026-03-03",
                        "items": [
                            {
                                "start": "2026-03-03 08:00:00",
                                "end": "2026-03-03 10:00:00",
                                "text": "08:00-10:00 OP10 legacy",
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
        ]
    }

    out = decorate_resource_dispatch_payload(payload)

    cell = out["calendar_rows"][0]["cells"][0]
    assert cell["items"][0]["text"] == "08:00-10:00 OP10 legacy"
    assert cell["text"] == "08:00-10:00 OP10 legacy"


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
