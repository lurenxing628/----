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


def test_missing_graph_diagnostic_sections_return_visible_empty_state() -> None:
    assert empty_diagnostic_sections() == []
    sections = build_diagnostic_sections({"algo": {}}, selected_ver=7)

    assert [section["key"] for section in sections] == ["diagnostic_unavailable"]
    text_blob = "\n".join(_iter_text(sections[0]))
    assert "本版本没有生成排产诊断数据" in text_blob
    assert "刷新页面" in text_blob


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
        "设备安排情况",
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
    json.dumps(sections, ensure_ascii=False, allow_nan=False)
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
    assert "这轮还没排上的工序样本：3、4、5、6、7" in text_blob
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

    assert by_key["resource_bottleneck"]["status"] == "empty"
    assert "没有生成设备安排诊断" in by_key["resource_bottleneck"]["summary"]
    assert by_key["schedule_health"]["status"] == "unavailable"
    health_text = "\n".join(_iter_text(by_key["schedule_health"]))
    assert "图分析组件暂不可用" in health_text
    assert "networkx" not in health_text.lower()
    impact_text = "\n".join(_iter_text(by_key["impact_explanation"]))
    assert "本次未生成完整影响范围指标" in impact_text


def test_diagnostic_sections_tolerate_old_and_bad_summary_shapes() -> None:
    assert build_diagnostic_sections(None, selected_ver=7)[0]["key"] == "diagnostic_unavailable"
    assert build_diagnostic_sections({"algo": "bad"}, selected_ver=7)[0]["key"] == "diagnostic_unavailable"

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
        "resource_bottleneck",
        "delay_risk",
        "impact_explanation",
    ]
    by_key = {section["key"]: section for section in sections}
    assert by_key["resource_bottleneck"]["status"] == "error"
    assert "设备安排诊断数据格式异常" in by_key["resource_bottleneck"]["summary"]
    assert "没有生成设备安排诊断" not in by_key["resource_bottleneck"]["summary"]
    json.dumps(sections, ensure_ascii=False, allow_nan=False)


def test_analysis_context_exposes_visible_empty_diagnostic_state_until_business_exists() -> None:
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
    assert [section["key"] for section in ctx["diagnostic_sections"]] == ["diagnostic_unavailable"]
    assert "本版本没有生成排产诊断数据" in ctx["diagnostic_sections"][0]["summary"]


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


@pytest.mark.parametrize("raw_status", [None, "", "unknown", "future_status"])
def test_overall_health_unknown_graph_status_is_visible_and_not_ok(raw_status: Any) -> None:
    summary = _summary_with_graph({})
    graph_analysis = summary["algo"]["graph_analysis"]
    if raw_status is None:
        graph_analysis.pop("status", None)
    else:
        graph_analysis["status"] = raw_status

    sections = build_diagnostic_sections(summary, selected_ver=7)
    health = sections[0]
    graph_status_item = next(item for item in health["items"] if item["key"] == "graph_status")

    assert health["key"] == "schedule_health"
    assert health["status"] == "unknown"
    assert graph_status_item["level"] == "unknown"
    assert graph_status_item["value"] == "状态未知"
