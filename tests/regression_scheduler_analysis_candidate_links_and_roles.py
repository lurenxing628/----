from __future__ import annotations

import ast
from pathlib import Path

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


def _direct_string_assignments(path: str) -> set[str]:
    tree = ast.parse((PROJECT_ROOT / path).read_text(encoding="utf-8"))
    names: set[str] = set()
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
    )

    rows = list(payload["candidate_comparison_display"]["rows"])
    assert [row["role"] for row in rows] == [
        ROLE_ADOPTED,
        ROLE_BASELINE_BEST,
        ROLE_CRITICAL_BEST,
    ]
    assert [row["role_label"] for row in rows] == [
        "最终采用",
        "原算法最好",
        "重点工序优先方案最好",
    ]

    for row in rows:
        role = row["role"]
        links = list(row["links"])
        assert [link["label"] for link in links] == ["设备甘特图", "人员甘特图", "周计划", "资源排班"]
        urls = [link["url"] for link in links]
        assert all("version=7" in url for url in urls)
        assert all(f"plan_role={role}" in url for url in urls)
        assert "/scheduler/gantt?view=machine" in urls[0]
        assert "/scheduler/gantt?view=operator" in urls[1]
        assert "/scheduler/week-plan?" in urls[2]
        assert "/scheduler/resource-dispatch?" in urls[3]
