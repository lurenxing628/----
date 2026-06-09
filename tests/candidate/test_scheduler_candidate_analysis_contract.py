"""回归测试：/scheduler/analysis 排产分析页的方案对比契约——analysis_page 须按 adopted/baseline_best/critical_best 顺序构建候选对比行，复用共享的 plan_role 标签，标注 is_same_as_adopted/is_comparison/comparison_note，并让设备甘特/人员甘特/周计划/资源排班/超期清单链接保持 version、plan_role 及资源与日期上下文（resource_type/resource_id/batch_id/week_start 等）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, g

from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    VALID_PLAN_ROLES,
    SchedulePlanRoleOption,
    plan_role_label,
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


class _PlanRoleServiceBroken:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise ValueError(f"方案对比记录不完整：version={version}, role=baseline_best 指向的方案不存在。")

    def resolve_plan_view(self, version: int, role: Optional[str], scenario_id: Optional[str] = None) -> _PlanResolutionStub:
        return _PlanResolutionStub(int(version), role, [])


class _PlanRoleServiceDetailBroken:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise ValueError(f"方案对比明细缺少编号。version={version}")

    def resolve_plan_view(self, version: int, role: Optional[str], scenario_id: Optional[str] = None) -> _PlanResolutionStub:
        return _PlanResolutionStub(int(version), role, [])


class _PlanRoleServiceDetailBrokenOnResolve(_PlanRoleServiceStub):
    def resolve_plan(self, version: int, role: str) -> None:
        raise ValueError(f"方案对比明细没有找到对应排程。version={version}, role={role}")


class _PlanRoleServiceDriftOnResolve(_PlanRoleServiceStub):
    def resolve_plan(self, version: int, role: str) -> SimpleNamespace:
        return SimpleNamespace(
            selected_role=role,
            source_table=SOURCE_CANDIDATE_ROWS,
            candidate_id=999,
            candidate_key="other_candidate",
        )


class _PlanRoleServiceMissingAdopted:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise ValueError(f"方案对比记录不完整：version={version} 缺少正式采用方案。")

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


def _plan_role_options_with_baseline_source(source_table: str) -> List[SchedulePlanRoleOption]:
    detail_saved = "yes" if source_table == SOURCE_CANDIDATE_ROWS else "no"
    return [
        option
        if option.role != ROLE_BASELINE_BEST
        else SchedulePlanRoleOption(
            role=ROLE_BASELINE_BEST,
            source_table=source_table,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            candidate_label=option.candidate_label,
            candidate_kind=option.candidate_kind,
            candidate_status=option.candidate_status,
            detail_saved=detail_saved,
        )
        for option in _plan_role_options()
    ]


def _plan_role_options_for_baseline_adopted() -> List[SchedulePlanRoleOption]:
    return [
        option
        if option.role not in (ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)
        else SchedulePlanRoleOption(
            role=option.role,
            source_table=SOURCE_SCHEDULE if option.role == ROLE_BASELINE_BEST else SOURCE_CANDIDATE_ROWS,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            candidate_label=option.candidate_label,
            candidate_kind=option.candidate_kind,
            candidate_status=option.candidate_status,
            detail_saved="no" if option.role == ROLE_BASELINE_BEST else "yes",
        )
        for option in _plan_role_options()
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
    import web.routes.scheduler_analysis as route_mod

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


def test_analysis_route_builds_candidate_comparison_rows_with_shared_role_labels_and_links(monkeypatch) -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app(monkeypatch)

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path="/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
    )

    display = payload["candidate_comparison_display"]
    assert [row["role"] for row in display["rows"]] == [
        ROLE_ADOPTED,
        ROLE_BASELINE_BEST,
        ROLE_CRITICAL_BEST,
    ]
    assert [row["role_label"] for row in display["rows"]] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]
    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_ADOPTED]["role_label"] == plan_role_label(ROLE_ADOPTED)
    assert rows[ROLE_BASELINE_BEST]["role_label"] == plan_role_label(ROLE_BASELINE_BEST)
    assert rows[ROLE_CRITICAL_BEST]["role_label"] == plan_role_label(ROLE_CRITICAL_BEST)
    assert rows[ROLE_CRITICAL_BEST]["candidate_key"] == rows[ROLE_ADOPTED]["candidate_key"]
    assert rows[ROLE_CRITICAL_BEST]["is_same_as_adopted"] is True
    assert rows[ROLE_CRITICAL_BEST]["is_comparison"] is True
    assert "只作对比参考查看" in rows[ROLE_CRITICAL_BEST]["comparison_note"]
    assert rows[ROLE_ADOPTED]["is_comparison"] is False
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "对比参考方案" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "不能直接派工或反馈" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert display["skipped_candidate_labels"] == []
    assert display["baseline_missing_or_failed"] is False

    for role, row in rows.items():
        if role == ROLE_CRITICAL_BEST:
            assert row["detail_saved"] is True
            assert row["can_open_detail"] is True
            assert row["link_unavailable_reason"] == ""
        links = list(row["links"])
        assert [link["label"] for link in links] == ["设备甘特图", "人员甘特图", "周计划", "资源排班", "超期清单"]
        urls = [link["url"] for link in links]
        assert "/scheduler/gantt?view=machine" in urls[0]
        assert "/scheduler/gantt?view=operator" in urls[1]
        assert "/scheduler/week-plan?" in urls[2]
        assert "/scheduler/resource-dispatch?" in urls[3]
        assert "/reports/overdue?" in urls[4]
        assert all("version=7" in url for url in urls)
        assert all(f"plan_role={role}" in url for url in urls)
        assert links[2]["target_page"] == "week_plan"
        assert links[2]["disabled"] is False
        assert "week_start=2026-05-25" in links[2]["url"]
        assert "required_params" in links[2]
        assert links[4]["target_page"] == "overdue_report"

    assert plan_role_service.version_queries == [7]
    json.dumps(payload, ensure_ascii=False)


def test_analysis_candidate_links_keep_resource_and_date_context(monkeypatch) -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app(monkeypatch)

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path=(
            "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31"
            "&query_date=2026-05-28&period_preset=week&resource_type=machine&resource_id=M1&batch_id=B-001"
        ),
    )

    row = {item["role"]: item for item in payload["candidate_comparison_display"]["rows"]}[ROLE_ADOPTED]
    links = {link["label"]: link for link in row["links"]}

    for label in ("设备甘特图", "人员甘特图"):
        assert "start_date=2026-05-25" in links[label]["url"]
        assert "end_date=2026-05-31" in links[label]["url"]
        assert "gantt_batch=B-001" in links[label]["url"]
    assert "gantt_resource=M1" in links["设备甘特图"]["url"]
    assert "gantt_resource" not in links["人员甘特图"]["url"]

    assert "date_from=2026-05-25" in links["周计划"]["url"]
    assert "date_to=2026-05-31" in links["周计划"]["url"]
    assert "week_start=2026-05-25" in links["周计划"]["url"]
    assert "resource_type=machine" in links["周计划"]["url"]
    assert "resource_id=M1" in links["周计划"]["url"]
    assert "batch_id=B-001" in links["周计划"]["url"]

    dispatch_url = links["资源排班"]["url"]
    assert "date_from=2026-05-25" in dispatch_url
    assert "date_to=2026-05-31" in dispatch_url
    assert "scope_type=machine" in dispatch_url
    assert "scope_id=M1" in dispatch_url
    assert "machine_id=M1" in dispatch_url
    assert "period_preset=custom" in dispatch_url
    assert "query_date=2026-05-28" in dispatch_url
    assert "batch_id=B-001" in dispatch_url
    assert "batch_id=B-001" in links["超期清单"]["url"]
