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


class _PlanRoleServiceStub:
    def __init__(self, options: Iterable[SchedulePlanRoleOption]):
        self.options = list(options)
        self.version_queries: List[int] = []

    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        self.version_queries.append(int(version))
        return list(self.options)


class _PlanRoleServiceMustNotBeCalled:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise AssertionError(f"没有方案对比数据时不应该查询方案角色，version={version}")


class _PlanRoleServiceBroken:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise ValueError(f"候选方案角色映射损坏：version={version}, role=baseline_best 指向的候选不存在。")


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


def _build_app() -> Tuple[Flask, Any]:
    _reset_scheduler_modules()
    import web.routes.scheduler_analysis as route_mod

    def _render_context(_tpl: str, **ctx: Any) -> Dict[str, Any]:
        return ctx

    route_mod.render_template = _render_context

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


def test_analysis_route_builds_candidate_comparison_rows_with_shared_role_labels_and_links() -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
    )

    display = payload["candidate_comparison_display"]
    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_ADOPTED]["role_label"] == plan_role_label(ROLE_ADOPTED)
    assert rows[ROLE_BASELINE_BEST]["role_label"] == plan_role_label(ROLE_BASELINE_BEST)
    assert rows[ROLE_CRITICAL_BEST]["role_label"] == plan_role_label(ROLE_CRITICAL_BEST)
    assert rows[ROLE_CRITICAL_BEST]["candidate_key"] == rows[ROLE_ADOPTED]["candidate_key"]
    assert rows[ROLE_CRITICAL_BEST]["is_same_as_adopted"] is True
    assert rows[ROLE_CRITICAL_BEST]["is_comparison"] is False
    assert (
        "与最终采用方案相同" in rows[ROLE_CRITICAL_BEST]["comparison_note"]
        or "正式排程已写入这一版" in rows[ROLE_CRITICAL_BEST]["comparison_note"]
    )
    assert rows[ROLE_ADOPTED]["is_comparison"] is False
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "对比方案" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "这是对比方案，不是正式写入的结果" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert display["skipped_candidate_labels"] == []
    assert display["baseline_missing_or_failed"] is False

    for role, row in rows.items():
        urls = [link["url"] for link in row["links"]]
        assert urls
        assert all("version=7" in url for url in urls)
        assert all(f"plan_role={role}" in url for url in urls)

    assert plan_role_service.version_queries == [7]
    json.dumps(payload, ensure_ascii=False)


def test_analysis_route_shows_clear_notice_when_candidate_comparison_is_missing() -> None:
    history_service = _HistoryServiceStub({"algo": {"metrics": {"overdue_count": 0}}})
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceMustNotBeCalled(),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert "本次没有开启方案对比，只生成了最终采用方案" in display["notice"]


def test_analysis_route_shows_incomplete_notice_when_candidate_detail_is_missing() -> None:
    summary = _comparison_summary(incomplete=True)
    comparison = summary["algo"]["candidate_comparison"]
    comparison["failed_candidate_count"] = 1
    comparison["baseline_missing_or_failed"] = True
    comparison["skipped_candidate_labels"] = ["重点工序优先方案 4/5"]
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceStub([]),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert display["failed_candidate_count"] == 1
    assert display["baseline_missing_or_failed"] is True
    assert display["skipped_candidate_labels"] == ["重点工序优先方案 4/5"]
    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "候选运行失败" in status_text
    assert "原算法候选缺失或失败" in status_text
    assert "因本次时间上限跳过" in status_text
    assert "本次方案对比记录不完整，当前只展示最终采用方案" in display["notice"]


def test_analysis_route_surfaces_plan_role_integrity_error_without_fake_links() -> None:
    summary = _comparison_summary(failed_extra=True)
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceBroken(),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert "本次方案对比记录不完整" in display["notice"]
    assert "角色映射损坏" in display["notice"]
    assert display["failed_candidate_count"] == 1
    assert not any(row.get("links") for row in display["rows"])


def test_analysis_template_uses_viewmodel_candidate_rows_and_route_built_links() -> None:
    source = (Path(__file__).resolve().parents[1] / "templates/scheduler/analysis.html").read_text(encoding="utf-8")

    assert "analysisCandidateComparisonTable" in source
    assert "candidate_comparison_display.rows" in source
    assert "row.comparison_note" in source
    assert "row.links" in source
    assert "candidate_comparison_display.status_messages" in source
    assert "message.class_name" in source
    assert "message.text" in source
    assert "plan_role=" not in source
    assert "关键链最好" not in source


def test_candidate_display_marks_baseline_best_as_adopted_when_baseline_is_selected() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(adopted_key="baseline"),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_BASELINE_BEST]["is_same_as_adopted"] is True
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is False
    assert "与最终采用方案相同" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert rows[ROLE_CRITICAL_BEST]["is_same_as_adopted"] is False
    assert rows[ROLE_CRITICAL_BEST]["is_comparison"] is True
    assert "这是对比方案，不是正式写入的结果" in rows[ROLE_CRITICAL_BEST]["comparison_note"]


def test_candidate_display_surfaces_non_representative_failed_candidates() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(failed_extra=True),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    assert display["failed_candidate_count"] == 1
    assert any("重点工序优先方案 5/5" in label for label in display["failed_candidate_labels"])
    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "候选运行失败" in status_text
    assert "重点工序优先方案 5/5" in status_text
    rows = {row["role"]: row for row in display["rows"]}
    assert set(rows) == {ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST}


def test_candidate_display_status_messages_include_candidate_run_state() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    comparison = summary["algo"]["candidate_comparison"]
    comparison["baseline_missing_or_failed"] = True
    comparison["skipped_candidate_labels"] = ["重点工序优先方案 4/5"]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "候选运行失败" in status_text
    assert "图分析失败：存在环" in status_text
    assert "原算法候选缺失或失败，本次采用结果需复核。" in status_text
    assert "因本次时间上限跳过：重点工序优先方案 4/5" in status_text


def test_candidate_display_and_plan_role_options_hide_old_internal_labels() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    visible_text = json.dumps(
        [(row["role_label"], row["candidate_label"]) for row in display["rows"]],
        ensure_ascii=False,
    )
    assert "关键链最好" not in visible_text
    assert "关键链候选" not in visible_text
    assert "graph_w" not in visible_text
    assert "重点工序优先方案" in visible_text

    option_text = json.dumps([option.to_dict() for option in _plan_role_options()], ensure_ascii=False)
    assert "关键链最好" not in option_text
    assert "关键链候选" not in option_text
    assert "重点工序优先方案" in option_text
