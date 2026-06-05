"""回归测试：/scheduler/analysis 候选对比展示的方案角色与跳转链接——三角色(adopted/baseline_best/critical_best)常量须仅在 core/models/schedule_plan_role.py 单点定义无重复，对比行按固定顺序与中文标签呈现并各带 5 个带 version/plan_role 的甘特/周计划/资源排班/超期链接；当候选明细未保存、代表候选状态为 failed/skipped/空/缺失时须隐藏链接并给出对应不可用原因。"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Set

from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
)
from tests.regression_scheduler_candidate_analysis_contract import (
    _build_app,
    _call_analysis_page,
    _comparison_summary,
    _HistoryServiceStub,
    _plan_role_options,
    _PlanRoleServiceStub,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_ROLE_CONSTANT_NAMES = {"ROLE_ADOPTED", "ROLE_BASELINE_BEST", "ROLE_CRITICAL_BEST"}
PLAN_SOURCE_CONSTANT_NAMES = {"SOURCE_SCHEDULE", "SOURCE_CANDIDATE_ROWS"}
PLAN_ROLE_CONSTANT_PATH = "core/models/schedule_plan_role.py"
PLAN_ROLE_COMPATIBILITY_FILES = (
    "core/services/scheduler/schedule_plan_query_service.py",
    "data/repositories/schedule_plan_query_repo.py",
    "core/services/scheduler/run/schedule_candidate_summary.py",
    "core/services/scheduler/run/schedule_candidate_persistence.py",
    "web/viewmodels/scheduler_analysis_candidates.py",
)


def _direct_string_assignments(path: str) -> Set[str]:
    tree = ast.parse((PROJECT_ROOT / path).read_text(encoding="utf-8"))
    names: Set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def test_candidate_role_and_source_constants_have_one_definition() -> None:
    assert {
        ROLE_ADOPTED,
        ROLE_BASELINE_BEST,
        ROLE_CRITICAL_BEST,
    } == {"adopted", "baseline_best", "critical_best"}

    canonical_assignments = _direct_string_assignments(PLAN_ROLE_CONSTANT_PATH)
    assert PLAN_ROLE_CONSTANT_NAMES <= canonical_assignments
    assert PLAN_SOURCE_CONSTANT_NAMES <= canonical_assignments

    protected_names = PLAN_ROLE_CONSTANT_NAMES | PLAN_SOURCE_CONSTANT_NAMES
    duplicates = {
        path: protected_names & _direct_string_assignments(path)
        for path in PLAN_ROLE_COMPATIBILITY_FILES
        if protected_names & _direct_string_assignments(path)
    }
    assert duplicates == {}


def test_analysis_candidate_links_and_roles_stay_stable() -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path="/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
    )

    rows = list(payload["candidate_comparison_display"]["rows"])
    assert [row["role"] for row in rows] == [
        ROLE_ADOPTED,
        ROLE_BASELINE_BEST,
        ROLE_CRITICAL_BEST,
    ]
    assert [row["role_label"] for row in rows] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]

    for row in rows:
        role = row["role"]
        links = list(row["links"])
        assert [link["label"] for link in links] == ["设备甘特图", "人员甘特图", "周计划", "资源排班", "超期清单"]
        urls = [link["url"] for link in links]
        assert all("version=7" in url for url in urls)
        assert all(f"plan_role={role}" in url for url in urls)
        assert "/scheduler/gantt?view=machine" in urls[0]
        assert "/scheduler/gantt?view=operator" in urls[1]
        assert "/scheduler/week-plan?" in urls[2]
        assert "week_start=2026-05-25" in urls[2]
        assert "/scheduler/resource-dispatch?" in urls[3]
        assert "/reports/overdue?" in urls[4]
        assert links[4]["target_page"] == "overdue_report"


def test_analysis_candidate_links_are_hidden_when_candidate_detail_is_not_saved() -> None:
    options = [
        option
        if option.role != ROLE_BASELINE_BEST
        else type(option)(
            role=option.role,
            source_table=option.source_table,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            candidate_label=option.candidate_label,
            candidate_kind=option.candidate_kind,
            candidate_status=option.candidate_status,
            detail_saved="no",
        )
        for option in _plan_role_options()
    ]
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(options)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    rows = {row["role"]: row for row in payload["candidate_comparison_display"]["rows"]}
    assert rows[ROLE_BASELINE_BEST]["links"] == {}
    assert rows[ROLE_BASELINE_BEST]["can_open_detail"] is False
    assert "这套对比参考方案没有保存明细" in rows[ROLE_BASELINE_BEST]["link_unavailable_reason"]
    assert rows[ROLE_ADOPTED]["links"]
    assert rows[ROLE_CRITICAL_BEST]["links"]


def test_analysis_candidate_links_are_hidden_when_representative_candidate_did_not_complete() -> None:
    summary = _comparison_summary()
    comparison = summary["algo"]["candidate_comparison"]
    for candidate in comparison["candidates"]:
        if candidate["candidate_key"] == comparison["baseline_best_candidate_key"]:
            candidate["status"] = "failed"
        if candidate["candidate_key"] == comparison["critical_best_candidate_key"]:
            candidate["status"] = "skipped"
    history_service = _HistoryServiceStub(summary)
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    rows = {row["role"]: row for row in payload["candidate_comparison_display"]["rows"]}
    assert rows[ROLE_BASELINE_BEST]["links"] == {}
    assert rows[ROLE_BASELINE_BEST]["can_open_detail"] is False
    assert "状态是失败" in rows[ROLE_BASELINE_BEST]["link_unavailable_reason"]
    assert rows[ROLE_CRITICAL_BEST]["links"] == {}
    assert rows[ROLE_CRITICAL_BEST]["can_open_detail"] is False
    assert "状态是已跳过" in rows[ROLE_CRITICAL_BEST]["link_unavailable_reason"]


def test_analysis_candidate_links_use_plan_option_status_when_summary_is_stale() -> None:
    options = [
        option
        if option.role != ROLE_BASELINE_BEST
        else type(option)(
            role=option.role,
            source_table=option.source_table,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            candidate_label=option.candidate_label,
            candidate_kind=option.candidate_kind,
            candidate_status="failed",
            detail_saved=option.detail_saved,
        )
        for option in _plan_role_options()
    ]
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(options)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    rows = {row["role"]: row for row in payload["candidate_comparison_display"]["rows"]}
    assert rows[ROLE_BASELINE_BEST]["links"] == {}
    assert rows[ROLE_BASELINE_BEST]["can_open_detail"] is False
    assert rows[ROLE_BASELINE_BEST]["status"] == "failed"
    assert "状态是失败" in rows[ROLE_BASELINE_BEST]["link_unavailable_reason"]


def test_analysis_candidate_links_are_hidden_when_plan_option_status_is_missing() -> None:
    options = [
        option
        if option.role != ROLE_BASELINE_BEST
        else type(option)(
            role=option.role,
            source_table=option.source_table,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            candidate_label=option.candidate_label,
            candidate_kind=option.candidate_kind,
            candidate_status=None,
            detail_saved=option.detail_saved,
        )
        for option in _plan_role_options()
    ]
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(options)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    rows = {row["role"]: row for row in payload["candidate_comparison_display"]["rows"]}
    assert rows[ROLE_BASELINE_BEST]["links"] == {}
    assert rows[ROLE_BASELINE_BEST]["can_open_detail"] is False
    assert rows[ROLE_BASELINE_BEST]["status"] == ""
    assert "状态没有确认" in rows[ROLE_BASELINE_BEST]["link_unavailable_reason"]


def test_analysis_candidate_links_are_hidden_when_summary_status_is_missing() -> None:
    summary = _comparison_summary()
    comparison = summary["algo"]["candidate_comparison"]
    for candidate in comparison["candidates"]:
        if candidate["candidate_key"] == comparison["baseline_best_candidate_key"]:
            candidate["status"] = ""
    history_service = _HistoryServiceStub(summary)
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    rows = {row["role"]: row for row in payload["candidate_comparison_display"]["rows"]}
    assert rows[ROLE_BASELINE_BEST]["links"] == {}
    assert rows[ROLE_BASELINE_BEST]["can_open_detail"] is False
    assert rows[ROLE_BASELINE_BEST]["status"] == ""
    assert "状态没有确认" in rows[ROLE_BASELINE_BEST]["link_unavailable_reason"]
