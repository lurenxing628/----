from __future__ import annotations

import json

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
