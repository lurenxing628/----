from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Iterable

import pytest

from core.services.scheduler.analysis.schedule_diagnostic_contract import (
    build_diagnostic_item,
    build_diagnostic_link,
    build_diagnostic_section,
    empty_diagnostic_sections,
)
from web.viewmodels.scheduler_analysis_diagnostics import build_diagnostic_sections
from web.viewmodels.scheduler_analysis_vm import build_analysis_context


def test_diagnostic_section_returns_complete_payload() -> None:
    link = build_diagnostic_link(label="查看明细", url="/scheduler/analysis", kind="page")
    item = build_diagnostic_item(
        key="missing_resource",
        label="缺资源数量",
        value=2,
        level="warning",
        message="有 2 个工序缺资源。",
        details=["设备未配置"],
        links=[link],
    )

    section = build_diagnostic_section(
        key="schedule_health",
        title="排产体检",
        status="warning",
        status_label="需要关注",
        summary="发现资源资料不完整。",
        items=[item],
        links=[link],
        degraded=True,
        degradation_events=[{"code": "resource_pool_degraded"}],
        empty_reason="",
    )

    assert set(section) == {
        "key",
        "title",
        "status",
        "status_label",
        "summary",
        "items",
        "links",
        "degraded",
        "degradation_events",
        "empty_reason",
    }
    assert set(item) == {"key", "label", "value", "level", "message", "details", "links"}
    assert set(link) == {"label", "url", "kind"}
    assert section["items"] == [item]
    assert section["links"] == [link]
    json.dumps(section, ensure_ascii=False)


def test_diagnostic_contract_uses_empty_lists_for_missing_collections() -> None:
    item = build_diagnostic_item(key="empty_item", label="空项", links=None, details=None)
    section = build_diagnostic_section(key="empty", title="空块", items=None, links=None, degradation_events=None)

    assert item["details"] == []
    assert item["links"] == []
    assert section["items"] == []
    assert section["links"] == []
    assert section["degradation_events"] == []


def test_diagnostic_contract_does_not_guess_success_when_status_missing() -> None:
    section = build_diagnostic_section(key="unknown", title="未知", status="")
    item = build_diagnostic_item(key="unknown_item", label="未知项", level="")

    assert section["status"] == "unknown"
    assert item["level"] == "unknown"


def test_empty_diagnostic_sections_returns_empty_list() -> None:
    assert empty_diagnostic_sections() == []
    assert build_diagnostic_sections({"algo": {}}, selected_ver=7) == []


def _full_graph_summary() -> Dict[str, Any]:
    return {
        "counts": {"total_ops": 4, "scheduled_ops": 4, "failed_ops": 0},
        "unscheduled_batch_count": 0,
        "invalid_due_count": 0,
        "overdue_batches": {"count": 1},
        "algo": {
            "graph_analysis": {
                "status": "available",
                "is_dag": True,
                "node_count": 4,
                "edge_count": 3,
                "critical_path_minutes": 180,
                "critical_path_node_count": 3,
                "warning_count": 1,
                "cycle_edge_count": 0,
                "time_cost_ms": 8,
                "resource_matching": {
                    "status": "available",
                    "reason": "ok",
                    "ready_operation_count": 3,
                    "operation_with_candidate_count": 2,
                    "machine_count": 2,
                    "edge_count": 4,
                    "matched_operation_count": 2,
                    "unmatched_operation_count": 1,
                    "bottleneck_machine_count": 1,
                },
            },
            "metrics": {
                "overdue_count": 1,
                "total_tardiness_hours": 2.5,
            },
        },
        "diagnostics": {
            "graph_analysis": {
                "critical_path_sample": ["op:B001:OP010:1", "op:B001:OP020:2"],
                "critical_path_count": 2,
                "critical_path_truncated": False,
                "node_metrics_status": "available",
                "node_metrics_sample": [
                    {
                        "node_id": "op:B001:OP010:1",
                        "critical_path_rank": 0,
                        "impact_count": 3,
                        "generation_index": 0,
                        "downstream_critical_minutes": 180,
                    }
                ],
                "graph_score_sample": [
                    {
                        "op_id": 1,
                        "impact_count": 3,
                        "downstream_critical_minutes": 180,
                        "bonus": 530,
                        "priority_key": [-530.0, 0.0],
                    }
                ],
                "warnings_sample": [
                    {
                        "code": "GRAPH_WARNING",
                        "message": "图分析提醒",
                        "data": {
                            "raw": "不要展示",
                        },
                    }
                ],
                "resource_matching": {
                    "unmatched_operation_ids_sample": ["3", "4", "5", "6", "7", "8"],
                    "bottleneck_machine_ids_sample": ["M1"],
                    "matches_sample": [
                        {"operation_id": "1", "machine_id": "M1", "candidate_machine_ids": ["M1", "M2"]}
                    ],
                    "resource_pool": {"M1": []},
                    "nodes": ["不要展示"],
                    "edges": ["不要展示"],
                    "raw": {"不要展示": True},
                },
            }
        },
    }


def _summary_with_graph(graph_analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "counts": {"failed_ops": 0},
        "algo": {
            "graph_analysis": {
                "status": "available",
                "is_dag": True,
                "node_count": 4,
                "edge_count": 3,
                "critical_path_minutes": 0,
                "critical_path_node_count": 0,
                "warning_count": 0,
                "cycle_edge_count": 0,
                "time_cost_ms": 1,
                **graph_analysis,
            },
            "metrics": {"overdue_count": 0, "total_tardiness_hours": 0},
        },
    }


def _iter_text(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_text(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text(item)
    elif value is not None:
        yield str(value)


def test_business_diagnostic_sections_cover_four_expected_blocks() -> None:
    summary = _full_graph_summary()
    before = deepcopy(summary)

    sections = build_diagnostic_sections(summary, selected_ver=7)

    assert [section["key"] for section in sections] == [
        "schedule_health",
        "resource_bottleneck",
        "delay_risk",
        "impact_explanation",
    ]
    assert [section["title"] for section in sections] == [
        "排产体检",
        "资源卡点",
        "延期风险",
        "影响解释",
    ]
    assert all(section["status_label"] for section in sections)
    assert all(set(section) == {
        "key",
        "title",
        "status",
        "status_label",
        "summary",
        "items",
        "links",
        "degraded",
        "degradation_events",
        "empty_reason",
    } for section in sections)
    json.dumps(sections, ensure_ascii=False)
    assert summary == before


def test_diagnostic_sections_translate_statuses_to_business_levels() -> None:
    summary = _full_graph_summary()

    sections = build_diagnostic_sections(summary, selected_ver=7)
    by_key = {section["key"]: section for section in sections}

    assert by_key["schedule_health"]["status"] == "warning"
    assert by_key["resource_bottleneck"]["status"] == "warning"
    assert by_key["delay_risk"]["status"] == "warning"
    assert by_key["impact_explanation"]["status"] == "warning"
    assert "第一批可排工序里有 1 道" in by_key["resource_bottleneck"]["summary"]
    assert "以下只展示本次诊断采样，不是完整清单。" == by_key["impact_explanation"]["summary"]


def test_diagnostic_sections_keep_diagnostics_samples_limited_and_safe() -> None:
    sections = build_diagnostic_sections(_full_graph_summary(), selected_ver=7)
    text_blob = "\n".join(_iter_text(sections))

    assert "以下只是样本，不是完整清单。" in text_blob
    assert "未匹配工序样本：3、4、5、6、7" in text_blob
    for forbidden in (
        "首波 ready",
        "candidate_machine_ids",
        "resource_pool",
        "nodes",
        "edges",
        "raw",
        "不要展示",
        "priority_key",
    ):
        assert forbidden not in text_blob


def test_diagnostic_sections_handle_unavailable_and_basic_report_samples() -> None:
    summary = {
        "algo": {
            "graph_analysis": {
                "status": "unavailable",
                "reason": "networkx_unavailable",
                "message": "缺少可选依赖 networkx==3.1",
                "node_count": 0,
                "edge_count": 0,
                "critical_path_minutes": 0,
                "critical_path_node_count": 0,
                "warning_count": 0,
                "cycle_edge_count": 0,
                "time_cost_ms": 3,
            }
        },
        "diagnostics": {
            "graph_analysis": {
                "critical_path_sample": ["op:1"],
                "node_metrics_status": "skipped_basic_report",
            }
        },
    }

    sections = build_diagnostic_sections(summary, selected_ver=8)
    by_key = {section["key"]: section for section in sections}

    assert "resource_bottleneck" not in by_key
    assert by_key["schedule_health"]["status"] == "unavailable"
    health_text = "\n".join(_iter_text(by_key["schedule_health"]))
    assert "图分析组件暂不可用" in health_text
    assert "networkx" not in health_text.lower()
    impact_text = "\n".join(_iter_text(by_key["impact_explanation"]))
    assert "本次未生成完整影响范围指标" in impact_text


def test_diagnostic_sections_tolerate_old_and_bad_summary_shapes() -> None:
    assert build_diagnostic_sections(None, selected_ver=7) == []
    assert build_diagnostic_sections({"algo": "bad"}, selected_ver=7) == []

    sections = build_diagnostic_sections(
        {
            "counts": "bad",
            "algo": {
                "graph_analysis": {
                    "status": "available",
                    "is_dag": "bad",
                    "node_count": "not-int",
                    "edge_count": None,
                    "critical_path_minutes": object(),
                    "critical_path_node_count": [],
                    "warning_count": {},
                    "cycle_edge_count": (),
                    "time_cost_ms": "bad",
                    "resource_matching": "bad",
                },
                "metrics": "bad",
            },
            "diagnostics": {"graph_analysis": {"warnings_sample": [{"data": [object()]}]}},
        },
        selected_ver=9,
    )

    assert [section["key"] for section in sections] == [
        "schedule_health",
        "delay_risk",
        "impact_explanation",
    ]
    json.dumps(sections, ensure_ascii=False)


def test_analysis_context_exposes_empty_diagnostic_sections_until_business_exists() -> None:
    summary = {
        "algo": {
            "objective": "min_changeover",
            "best_score_schema": [
                {"index": 0, "key": "failed_ops", "label": "失败工序数"},
                {"index": 1, "key": "changeover_count", "label": "换型次数"},
            ],
            "metrics": {"changeover_count": 1},
        }
    }

    ctx = build_analysis_context(
        selected_ver=7,
        raw_hist=[{"version": 7, "result_summary": summary}],
        selected_item={"version": 7, "result_summary": summary},
    )

    assert "diagnostic_sections" in ctx
    assert ctx["diagnostic_sections"] == []


def test_analysis_context_exposes_business_diagnostic_sections() -> None:
    summary = _full_graph_summary()

    ctx = build_analysis_context(
        selected_ver=7,
        raw_hist=[{"version": 7, "result_summary": summary}],
        selected_item={"version": 7, "result_summary": summary},
    )

    assert [section["key"] for section in ctx["diagnostic_sections"]] == [
        "schedule_health",
        "resource_bottleneck",
        "delay_risk",
        "impact_explanation",
    ]


@pytest.mark.parametrize(
    ("graph_analysis", "expected_status"),
    [
        ({}, "ok"),
        ({"is_dag": False}, "danger"),
        ({"cycle_edge_count": 2}, "danger"),
        ({"status": "unavailable", "reason": "networkx_unavailable"}, "unavailable"),
        ({"status": "input_error"}, "error"),
        ({"status": "build_error"}, "error"),
    ],
)
def test_overall_health_section_status_scenarios(
    graph_analysis: Dict[str, Any],
    expected_status: str,
) -> None:
    sections = build_diagnostic_sections(_summary_with_graph(graph_analysis), selected_ver=7)

    assert sections[0]["key"] == "schedule_health"
    assert sections[0]["status"] == expected_status


@pytest.mark.parametrize(
    ("resource_matching", "expected_status", "expected_summary"),
    [
        (
            {
                "status": "available",
                "reason": "ok",
                "ready_operation_count": 2,
                "operation_with_candidate_count": 2,
                "machine_count": 2,
                "edge_count": 4,
                "matched_operation_count": 2,
                "unmatched_operation_count": 0,
                "bottleneck_machine_count": 0,
            },
            "ok",
            "第一批可排工序都有可用设备可用。",
        ),
        (
            {
                "status": "available",
                "reason": "ok",
                "ready_operation_count": 2,
                "operation_with_candidate_count": 1,
                "machine_count": 1,
                "edge_count": 1,
                "matched_operation_count": 1,
                "unmatched_operation_count": 1,
                "bottleneck_machine_count": 0,
            },
            "warning",
            "第一批可排工序里有 1 道暂时找不到可用设备。",
        ),
        (
            {
                "status": "empty",
                "reason": "empty_ready_set",
                "ready_operation_count": 0,
            },
            "empty",
            "本次暂无第一批可排工序可做资源匹配。",
        ),
        (
            {
                "status": "skipped",
                "reason": "graph_not_dag",
                "ready_operation_count": 0,
            },
            "warning",
            "工序关系异常，资源匹配诊断已跳过。",
        ),
        (
            {
                "status": "error",
                "reason": "graph_resource_matching_contract_error",
                "ready_operation_count": 0,
            },
            "error",
            "资源匹配诊断异常，本次不展示资源匹配结果。",
        ),
    ],
)
def test_resource_bottleneck_section_status_scenarios(
    resource_matching: Dict[str, Any],
    expected_status: str,
    expected_summary: str,
) -> None:
    sections = build_diagnostic_sections(
        _summary_with_graph({"resource_matching": resource_matching}),
        selected_ver=7,
    )
    resource_section = next(section for section in sections if section["key"] == "resource_bottleneck")

    assert resource_section["status"] == expected_status
    assert resource_section["summary"] == expected_summary


@pytest.mark.parametrize(
    ("summary_patch", "expected_status"),
    [
        ({"counts": {"failed_ops": 1}}, "danger"),
        ({"unscheduled_batch_count": 1}, "warning"),
        ({"algo": {"metrics": {"overdue_count": 1, "total_tardiness_hours": 2}}}, "warning"),
        ({"algo": {"metrics": {"overdue_count": 0, "total_tardiness_hours": 2.5}}}, "warning"),
        ({"algo": {"graph_analysis": {"critical_path_minutes": 120}}}, "notice"),
        ({}, "ok"),
    ],
)
def test_delay_risk_section_status_scenarios(
    summary_patch: Dict[str, Any],
    expected_status: str,
) -> None:
    summary = _summary_with_graph({})
    if "counts" in summary_patch:
        summary["counts"].update(summary_patch["counts"])
    if "unscheduled_batch_count" in summary_patch:
        summary["unscheduled_batch_count"] = summary_patch["unscheduled_batch_count"]
    if "algo" in summary_patch:
        patch_algo = summary_patch["algo"]
        if "metrics" in patch_algo:
            summary["algo"]["metrics"].update(patch_algo["metrics"])
        if "graph_analysis" in patch_algo:
            summary["algo"]["graph_analysis"].update(patch_algo["graph_analysis"])

    sections = build_diagnostic_sections(summary, selected_ver=7)
    delay_section = next(section for section in sections if section["key"] == "delay_risk")

    assert delay_section["status"] == expected_status
