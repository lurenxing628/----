"""Explicit analysis unit fixtures copied from the 36bae candidate contract.

Inputs are the monkeypatch object, summary, role service and request path.
This module imports no collected tests and never opens an application database.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, g

from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SchedulePlanRoleOption,
)
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE


class _HistoryItem:
    def __init__(self, version: int, summary: Dict[str, Any]):
        self.version = int(version)
        self._summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "schedule_time": "2026-05-19 10:00",
            "strategy": "improve",
            "result_status": "success",
            "created_by": "web",
            "result_summary": self._summary,
        }


class _HistoryServiceStub:
    def __init__(self, summary: Dict[str, Any]):
        self.summary = summary
        self.version_queries: List[int] = []
        self.recent_limits: List[int] = []

    def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [{"version": 7, "result_status": "success"}]

    def get_latest_version(self) -> int:
        return 7

    def get_by_version(self, version: int) -> _HistoryItem:
        self.version_queries.append(int(version))
        return _HistoryItem(int(version), self.summary)

    def list_recent(self, limit: int = 400) -> List[_HistoryItem]:
        self.recent_limits.append(limit)
        return [_HistoryItem(7, self.summary)]


class _PlanResolutionStub:
    def __init__(self, version: int, requested_role: Optional[str], options: Iterable[SchedulePlanRoleOption]):
        role = str(requested_role or ROLE_ADOPTED)
        options_by_role = {item.role: item for item in options}
        selected = options_by_role.get(role) or options_by_role.get(ROLE_ADOPTED)
        self.version = int(version)
        self.requested_role = role
        self.selected_role = selected.role if selected else ROLE_ADOPTED
        self.source_table = selected.source_table if selected else SOURCE_SCHEDULE
        self.candidate_id = selected.candidate_id if selected else None
        self.candidate_key = selected.candidate_key if selected else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "requested_role": self.requested_role,
            "selected_role": self.selected_role,
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "status": "resolved_adopted" if self.selected_role == ROLE_ADOPTED else "resolved_comparison",
            "is_scenario_preview": False,
            "is_comparison": self.selected_role != ROLE_ADOPTED,
            "is_superseded_by_newer_version": False,
            "can_dispatch": False,
            "can_write_feedback": False,
        }


class _PlanRoleServiceStub:
    def __init__(self, options: Iterable[SchedulePlanRoleOption]):
        self.options = list(options)
        self.version_queries: List[int] = []

    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        self.version_queries.append(int(version))
        return list(self.options)

    def resolve_plan_view(self, version: int, role: Optional[str], scenario_id: Optional[str] = None) -> _PlanResolutionStub:
        return _PlanResolutionStub(int(version), role, self.options)


class _PlanRoleServiceMustNotBeCalled:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise AssertionError(f"没有方案对比数据时不应该查询方案角色，version={version}")

    def resolve_plan_view(self, version: int, role: Optional[str], scenario_id: Optional[str] = None) -> _PlanResolutionStub:
        return _PlanResolutionStub(int(version), role, [])


def _comparison_summary(
    *,
    adopted_key: str = "graph_w1_of_5",
    failed_extra: bool = False,
    incomplete: bool = False,
) -> Dict[str, Any]:
    baseline_roles = [ROLE_BASELINE_BEST]
    critical_roles = [ROLE_CRITICAL_BEST]
    if adopted_key == "baseline":
        baseline_roles.append(ROLE_ADOPTED)
    if adopted_key == "graph_w1_of_5":
        critical_roles.append(ROLE_ADOPTED)

    candidates = [
        {
            "candidate_key": "baseline",
            "label": "原算法候选",
            "kind": "baseline",
            "status": "completed",
            "score": [0, 0, 12.0],
            "metrics": {
                "failed_ops": 0,
                "overdue_count": 0,
                "total_tardiness_hours": 0,
                "weighted_tardiness_hours": 6.0,
                "makespan_hours": 12.0,
                "changeover_count": 2,
            },
            "roles": baseline_roles,
        },
        {
            "candidate_key": "graph_w1_of_5",
            "label": "graph_w1_of_5",
            "kind": "critical_chain",
            "status": "completed",
            "score": [0, 0, 9.0],
            "metrics": {
                "failed_ops": 0,
                "overdue_count": 0,
                "total_tardiness_hours": 0,
                "weighted_tardiness_hours": 8.0,
                "makespan_hours": 9.0,
                "changeover_count": 1,
            },
            "roles": critical_roles,
        },
    ]
    if failed_extra:
        candidates.append(
            {
                "candidate_key": "graph_w5_of_5",
                "label": "重点工序优先方案 5/5",
                "kind": "critical_chain",
                "status": "failed",
                "failure_reason": "图分析失败：存在环",
                "score": [],
                "metrics": {},
                "roles": [],
            }
        )
    if incomplete:
        candidates = []

    return {
        "algo": {
            "metrics": {"overdue_count": 0},
            "candidate_comparison": {
                "enabled": True,
                "planned_candidate_count": 6 if failed_extra else 3,
                "completed_candidate_count": 5 if failed_extra else 3,
                "failed_candidate_count": 1 if failed_extra else 0,
                "skipped_candidate_count": 0,
                "skipped_candidate_labels": [],
                "baseline_missing_or_failed": False,
                "adopted_candidate_key": adopted_key,
                "baseline_best_candidate_key": "baseline",
                "critical_best_candidate_key": "graph_w1_of_5",
                "candidates": candidates,
            },
        }
    }


def _plan_role_options() -> List[SchedulePlanRoleOption]:
    return [
        SchedulePlanRoleOption(
            role=ROLE_ADOPTED,
            source_table=SOURCE_SCHEDULE,
            candidate_id=1,
            candidate_key="graph_w1_of_5",
            candidate_label="重点工序优先方案 1/5",
            candidate_kind="critical_chain",
            candidate_status="completed",
            detail_saved="no",
        ),
        SchedulePlanRoleOption(
            role=ROLE_BASELINE_BEST,
            source_table=SOURCE_CANDIDATE_ROWS,
            candidate_id=2,
            candidate_key="baseline",
            candidate_label="原算法候选",
            candidate_kind="baseline",
            candidate_status="completed",
            detail_saved="yes",
        ),
        SchedulePlanRoleOption(
            role=ROLE_CRITICAL_BEST,
            source_table=SOURCE_SCHEDULE,
            candidate_id=1,
            candidate_key="graph_w1_of_5",
            candidate_label="重点工序优先方案 1/5",
            candidate_kind="critical_chain",
            candidate_status="completed",
            detail_saved="no",
        ),
    ]


def _reset_scheduler_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)


def _add_plan_target_routes(app: Flask) -> None:
    def _noop() -> str:
        return ""

    app.add_url_rule("/scheduler/gantt", endpoint="scheduler.gantt_page", view_func=_noop)
    app.add_url_rule("/scheduler/week-plan", endpoint="scheduler.week_plan_page", view_func=_noop)
    app.add_url_rule("/scheduler/resource-dispatch", endpoint="scheduler.resource_dispatch_page", view_func=_noop)


def _build_app(monkeypatch) -> Tuple[Flask, Any]:
    _reset_scheduler_modules()
    import web.routes.domains.scheduler.scheduler_analysis as route_mod

    def _render_context(_tpl: str, **ctx: Any) -> Dict[str, Any]:
        return ctx

    monkeypatch.setattr(route_mod, "render_template", _render_context)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-candidate-analysis"
    _add_plan_target_routes(app)
    return app, route_mod


def _call_analysis_page(
    app: Flask,
    route_mod: Any,
    *,
    history_service: _HistoryServiceStub,
    plan_role_service: Optional[Any],
    path: str = "/scheduler/analysis?version=7",
) -> Dict[str, Any]:
    with app.test_request_context(path):
        g.services = SimpleNamespace(
            schedule_history_query_service=history_service,
            schedule_plan_query_service=plan_role_service,
        )
        g.app_logger = app.logger
        g.op_logger = None
        return route_mod.analysis_page()

