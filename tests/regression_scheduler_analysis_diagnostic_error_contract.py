"""回归测试：排产分析诊断的异常与边界口径——safe_int/safe_float/format_hours 对 NaN/Inf/超大值等非有限数抛 ValueError（仅 None 才用 default）；build_diagnostic_sections 把非有限数标成「无法安全展示」并将对应分节置为 error/degraded、不臆造 0，且不吞没真实异常；资源瓶颈与延期风险分节按 resource_matching/summary 输出对应 status 与中文摘要。"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
from regression_scheduler_analysis_diagnostic_contract import (
    _full_graph_summary,
    _iter_text,
    _summary_with_graph,
)

import web.viewmodels.scheduler_analysis_diagnostics as diagnostics
from web.viewmodels.scheduler_analysis_diagnostic_helpers import format_hours, safe_float, safe_int
from web.viewmodels.scheduler_analysis_diagnostics import build_diagnostic_sections


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", "-Infinity", "1e9999"])
def test_diagnostic_numeric_helpers_reject_non_finite_numbers(bad_value: Any) -> None:
    with pytest.raises(ValueError):
        safe_int(bad_value)
    with pytest.raises(ValueError):
        safe_float(bad_value)
    with pytest.raises(ValueError):
        format_hours(bad_value)


@pytest.mark.parametrize("bad_value", ["not-int", object(), [], {}])
def test_diagnostic_numeric_helpers_reject_bad_values_instead_of_defaulting(bad_value: Any) -> None:
    with pytest.raises(ValueError):
        safe_int(bad_value, default=7)
    with pytest.raises(ValueError):
        safe_float(bad_value, default=7.5)


def test_diagnostic_numeric_helpers_only_default_when_value_is_missing() -> None:
    assert safe_int(None, default=7) == 7
    assert safe_float(None, default=7.5) == 7.5


@pytest.mark.parametrize(
    ("mutator", "expected_section_key"),
    [
        (lambda summary: summary["algo"]["graph_analysis"].__setitem__("time_cost_ms", float("inf")), "schedule_health"),
        (lambda summary: summary["algo"]["graph_analysis"].__setitem__("warning_count", float("nan")), "schedule_health"),
        (lambda summary: summary["algo"]["metrics"].__setitem__("total_tardiness_hours", "Infinity"), "delay_risk"),
        (
            lambda summary: summary["algo"]["graph_analysis"]["resource_matching"].__setitem__("ready_operation_count", float("inf")),
            "resource_bottleneck",
        ),
        (
            lambda summary: summary["diagnostics"]["graph_analysis"]["node_metrics_sample"][0].__setitem__(
                "downstream_critical_minutes",
                "1e9999",
            ),
            "impact_explanation",
        ),
    ],
)
def test_diagnostic_sections_surface_non_finite_numbers_without_guessing_zero(
    mutator: Any,
    expected_section_key: str,
) -> None:
    summary = _full_graph_summary()
    mutator(summary)

    sections = build_diagnostic_sections(summary, selected_ver=7)

    json.dumps(sections, ensure_ascii=False, allow_nan=False)
    by_key = {section["key"]: section for section in sections}
    section = by_key[expected_section_key]
    item = next(item for item in section["items"] if item["key"] == "diagnostic_non_finite_number")

    assert section["status"] == "error"
    assert section["status_label"] == "诊断异常"
    assert section["degraded"] is True
    assert section["degradation_events"][0]["code"] == "diagnostic_non_finite_number"
    assert item["level"] == "danger"
    assert item["value"] == "无法安全展示"
    assert "非有限数字" in item["message"]
    text_blob = "\n".join(_iter_text(section))
    assert "0 毫秒" not in text_blob
    assert "0 分钟" not in text_blob
    assert "0 小时" not in text_blob


def test_diagnostic_sections_do_not_swallow_unexpected_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise RuntimeError("unexpected diagnostic bug")

    monkeypatch.setattr(diagnostics, "build_delay_risk_section", boom)

    with pytest.raises(RuntimeError, match="unexpected diagnostic bug"):
        diagnostics.build_diagnostic_sections(_summary_with_graph({}), selected_ver=7)


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
            "第一批可排工序都能找到设备。",
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
            "第一批可排工序里有 1 道还没配可用设备，请先检查工序设备配置。",
        ),
        (
            {
                "status": "available",
                "reason": "ok",
                "ready_operation_count": 180,
                "operation_with_candidate_count": 180,
                "machine_count": 18,
                "edge_count": 180,
                "matched_operation_count": 18,
                "unmatched_operation_count": 162,
                "bottleneck_machine_count": 18,
            },
            "warning",
            "第一批可排工序里有 162 道能找到设备，但这轮设备不够同时安排，后面还要继续排。",
        ),
        ({"status": "empty", "reason": "empty_ready_set", "ready_operation_count": 0}, "empty", "本次没有第一批可排工序可检查设备。"),
        ({"status": "skipped", "reason": "graph_not_dag", "ready_operation_count": 0}, "warning", "工序先后关系有问题，本次先不检查设备安排。"),
        ({"status": "error", "reason": "graph_resource_matching_contract_error", "ready_operation_count": 0}, "error", "检查设备安排时出错，本次不展示设备检查结果。"),
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
    text_blob = "\n".join(_iter_text(resource_section))
    if resource_matching.get("operation_with_candidate_count") == resource_matching.get("ready_operation_count"):
        assert "找不到可用设备" not in text_blob
        assert "未匹配到设备" not in text_blob
        assert "设备不够" in text_blob or "后面可能要排队" in text_blob or expected_status == "ok"


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
