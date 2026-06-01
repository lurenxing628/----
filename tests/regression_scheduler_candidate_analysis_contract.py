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
        raise ValueError(f"方案对比记录不完整：version={version}, role=baseline_best 指向的方案不存在。")


class _PlanRoleServiceDetailBroken:
    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        raise ValueError(f"方案对比明细缺少编号。version={version}")


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


def test_analysis_candidate_links_keep_resource_and_date_context() -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

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
        assert "resource_type=machine" in links[label]["url"]
        assert "resource_id=M1" in links[label]["url"]

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
    assert "period_preset=week" in dispatch_url
    assert "query_date=2026-05-28" in dispatch_url
    assert "batch_id=B-001" in dispatch_url
    assert "batch_id=B-001" in links["超期清单"]["url"]


def test_analysis_candidate_links_accept_start_end_date_aliases() -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path=(
            "/scheduler/analysis?version=7&start_date=2026-05-25&end_date=2026-05-31"
            "&period_preset=custom&resource_type=machine&resource_id=M1"
        ),
    )

    row = {item["role"]: item for item in payload["candidate_comparison_display"]["rows"]}[ROLE_ADOPTED]
    links = {link["label"]: link for link in row["links"]}

    assert "start_date=2026-05-25" in links["设备甘特图"]["url"]
    assert "end_date=2026-05-31" in links["人员甘特图"]["url"]
    assert "date_from=2026-05-25" in links["超期清单"]["url"]
    assert "date_to=2026-05-31" in links["超期清单"]["url"]
    assert "date_from=2026-05-25" in links["周计划"]["url"]
    assert "date_to=2026-05-31" in links["周计划"]["url"]
    assert "week_start=2026-05-25" in links["周计划"]["url"]
    assert "scope_type=machine" in links["资源排班"]["url"]
    assert "machine_id=M1" in links["资源排班"]["url"]
    assert "date_from=2026-05-25" in links["资源排班"]["url"]
    assert "date_to=2026-05-31" in links["资源排班"]["url"]
    assert "period_preset=custom" in links["资源排班"]["url"]


def test_analysis_candidate_links_without_date_are_disabled_with_reason() -> None:
    history_service = _HistoryServiceStub(_comparison_summary())
    plan_role_service = _PlanRoleServiceStub(_plan_role_options())
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path="/scheduler/analysis?version=7",
    )

    row = {item["role"]: item for item in payload["candidate_comparison_display"]["rows"]}[ROLE_ADOPTED]
    links = {link["label"]: link for link in row["links"]}

    for label in ("设备甘特图", "人员甘特图", "资源排班", "超期清单"):
        assert links[label]["disabled"] is True
        assert links[label]["url"] == ""
        assert "日期范围" in links[label]["disabled_reason"]

    assert links["周计划"]["disabled"] is True
    assert links["周计划"]["url"] == ""
    assert "日期范围" in links["周计划"]["disabled_reason"]


def test_analysis_route_hides_candidate_links_when_detail_was_not_saved() -> None:
    options = [
        option
        if option.role != ROLE_BASELINE_BEST
        else SchedulePlanRoleOption(
            role=option.role,
            source_table=SOURCE_CANDIDATE_ROWS,
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
    baseline = rows[ROLE_BASELINE_BEST]
    assert baseline["plan_role_available"] is True
    assert baseline["detail_saved"] is False
    assert baseline["can_open_detail"] is False
    assert baseline["links"] == {}
    assert baseline["link_unavailable_reason"] == "这套对比参考方案没有保存明细，当前无法查看明细。"
    assert rows[ROLE_ADOPTED]["links"]
    assert rows[ROLE_CRITICAL_BEST]["links"]


def test_analysis_candidate_display_keeps_core_role_order_and_labels() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    assert [row["role"] for row in display["rows"]] == list(VALID_PLAN_ROLES)
    assert [row["role_label"] for row in display["rows"]] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]
    assert [card["role_label"] for card in display["summary_cards"]] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]
    assert len(display["summary_cards"]) == 3


def test_candidate_summary_cards_use_adopted_plan_as_only_baseline() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_ADOPTED]["weighted_tardiness_hours"] == 8.0
    assert rows[ROLE_BASELINE_BEST]["weighted_tardiness_hours"] == 6.0

    cards = {card["role_label"]: card for card in display["summary_cards"]}
    adopted_metrics = {metric["label"]: metric for metric in cards["正式采用方案"]["metrics"]}
    baseline_metrics = {metric["label"]: metric for metric in cards["原算法代表方案"]["metrics"]}

    assert adopted_metrics["总工期"]["comparison_text"] == "作为对比基准"
    assert baseline_metrics["总工期"]["value"] == "12 小时"
    assert baseline_metrics["总工期"]["comparison_text"] == "比正式采用方案多了 3 小时"
    assert baseline_metrics["加权拖期"]["comparison_text"] == "比正式采用方案少了 2 小时"
    assert baseline_metrics["失败工序"]["comparison_text"] == "和正式采用方案基本持平"


def test_candidate_summary_cards_stay_to_three_representative_roles_only() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    comparison = summary["algo"]["candidate_comparison"]
    comparison["candidates"].append(
        {
            "candidate_key": "graph_w2_of_5",
            "label": "重点工序优先方案 2/5",
            "kind": "critical_chain",
            "status": "completed",
            "score": [0, 0, 8.0],
            "metrics": {
                "failed_ops": 0,
                "overdue_count": 0,
                "total_tardiness_hours": 0,
                "weighted_tardiness_hours": 4.0,
                "makespan_hours": 8.0,
                "changeover_count": 3,
            },
            "roles": [],
            "batch_impacts": [{"batch_id": "B-001"}],
            "resource_impacts": [{"machine_id": "M-01"}],
        }
    )
    options = _plan_role_options() + [
        {
            "role": "fastest_plan",
            "source_table": SOURCE_CANDIDATE_ROWS,
            "candidate_id": 8,
            "candidate_key": "graph_w2_of_5",
            "candidate_label": "最快试算方案",
            "candidate_kind": "critical_chain",
            "candidate_status": "completed",
            "detail_saved": "yes",
        }
    ]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=options,
    )

    assert [card["role_label"] for card in display["summary_cards"]] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]
    visible_text = json.dumps(display["summary_cards"], ensure_ascii=False)
    assert "最快试算方案" not in visible_text
    assert "重点工序优先方案 2/5" not in visible_text
    assert "batch_impacts" not in visible_text
    assert "resource_impacts" not in visible_text


def test_candidate_summary_cards_show_plain_no_data_when_metrics_are_missing() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    candidates = summary["algo"]["candidate_comparison"]["candidates"]
    candidates[0]["metrics"].pop("makespan_hours")
    candidates[0]["metrics"].pop("changeover_count")

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    baseline = {
        card["role_label"]: card for card in display["summary_cards"]
    }["原算法代表方案"]
    metrics = {metric["label"]: metric for metric in baseline["metrics"]}

    assert metrics["总工期"]["value"] == "暂无数据"
    assert metrics["总工期"]["comparison_text"] == "暂无对比数据"
    assert metrics["换型次数"]["value"] == "暂无数据"
    visible_text = json.dumps(baseline, ensure_ascii=False)
    assert "None" not in visible_text
    assert "nan" not in visible_text
    assert "null" not in visible_text


def test_analysis_candidate_empty_role_label_stays_placeholder() -> None:
    from web.viewmodels.scheduler_analysis_candidates import _plan_role_label

    assert _plan_role_label("") == "-"
    assert _plan_role_label(None) == "-"


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
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "本次没有开启方案对比，只生成了正式采用方案" in display["notice"]


def test_analysis_route_shows_incomplete_notice_when_candidate_detail_is_missing() -> None:
    summary = _comparison_summary(incomplete=True)
    comparison = summary["algo"]["candidate_comparison"]
    comparison["failed_candidate_count"] = 1
    comparison["baseline_missing_or_failed"] = True
    comparison["skipped_candidate_labels"] = ["关键链候选 4/5"]
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
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert display["failed_candidate_count"] == 1
    assert display["baseline_missing_or_failed"] is True
    assert display["skipped_candidate_labels"] == ["重点工序优先方案 4/5"]
    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "试算方案没算成功" in status_text
    assert "原算法那套方案缺失或没算成功" in status_text
    assert "因为时间到了，系统没再开始这些方案" in status_text
    assert "本次方案对比记录不完整，当前只展示正式采用方案" in display["notice"]


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
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "本次方案对比记录不完整" in display["notice"]
    assert "方案对比记录里的跳转关系不完整" in display["notice"]
    assert display["failed_candidate_count"] == 1
    assert not any(row.get("links") for row in display["rows"])


def test_analysis_route_classifies_plan_role_detail_errors_before_missing_links() -> None:
    summary = _comparison_summary(failed_extra=True)
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceDetailBroken(),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "本次方案对比记录不完整" in display["notice"]
    assert "方案对比明细不完整" in display["notice"]
    assert "跳转关系不完整" not in display["notice"]


def test_analysis_route_validates_plan_role_targets_before_attaching_links() -> None:
    summary = _comparison_summary(failed_extra=True)
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceDetailBrokenOnResolve(_plan_role_options()),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "方案对比明细不完整" in display["notice"]
    assert not any(row.get("links") for row in display["rows"])


def test_analysis_route_rejects_plan_role_target_drift_before_attaching_links() -> None:
    summary = _comparison_summary(failed_extra=True)
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceDriftOnResolve(_plan_role_options()),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "方案对比明细不完整" in display["notice"]
    assert not any(row.get("links") for row in display["rows"])


def test_analysis_route_classifies_missing_adopted_role_without_link_notice() -> None:
    summary = _comparison_summary(failed_extra=True)
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()

    payload = _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=_PlanRoleServiceMissingAdopted(),
    )

    display = payload["candidate_comparison_display"]
    assert display["has_comparison"] is False
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "当前不展示方案对比" in display["notice"]
    assert "当前只展示正式采用方案" not in display["notice"]
    assert "方案对比记录缺少正式采用方案" in display["notice"]
    assert "跳转关系不完整" not in display["notice"]


def test_analysis_template_uses_viewmodel_candidate_rows_and_route_built_links() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "templates/scheduler/analysis_parts/_candidate_comparison.html"
    ).read_text(encoding="utf-8")

    assert "analysisCandidateComparisonTable" in source
    assert "candidate_comparison_display.rows" in source
    assert "row.comparison_note" in source
    assert "row.links" in source
    assert "link.disabled" in source
    assert "aria-disabled" in source
    assert "disabled_reason" in source
    assert "candidate_comparison_display.status_messages" in source
    assert "message.class_name" in source
    assert "message.text" in source
    assert "plan_role=" not in source
    assert "关键链最好" not in source
    assert "row.score_label" not in source
    assert ">评分<" not in source


def test_candidate_display_marks_baseline_best_as_adopted_when_baseline_is_selected() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(adopted_key="baseline"),
        selected_ver=7,
        plan_role_options=_plan_role_options_for_baseline_adopted(),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_BASELINE_BEST]["is_same_as_adopted"] is True
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "只作对比参考查看" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert rows[ROLE_CRITICAL_BEST]["is_same_as_adopted"] is False
    assert rows[ROLE_CRITICAL_BEST]["is_comparison"] is True
    assert "不能直接派工或反馈" in rows[ROLE_CRITICAL_BEST]["comparison_note"]


def test_candidate_display_uses_plan_role_source_table_for_comparison_state() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options_with_baseline_source(SOURCE_SCHEDULE),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_BASELINE_BEST]["candidate_key"] != rows[ROLE_ADOPTED]["candidate_key"]
    assert rows[ROLE_BASELINE_BEST]["source_table"] == SOURCE_SCHEDULE
    assert rows[ROLE_BASELINE_BEST]["is_same_as_adopted"] is False
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "对比参考方案" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "不能直接派工或反馈" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "正式排程已写入这一版" not in rows[ROLE_BASELINE_BEST]["comparison_note"]


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
    assert "试算方案没算成功" in status_text
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
    assert "试算方案没算成功" in status_text
    assert "图分析失败：存在环" in status_text
    assert "原算法那套方案缺失或没算成功，请复核这次采用的结果。" in status_text
    assert "因为时间到了，系统没再开始这些方案：重点工序优先方案 4/5" in status_text
    assert "候选运行失败" not in status_text
    assert "时间上限" not in status_text
    assert "原算法候选" not in status_text
    assert "关键链候选" not in status_text


def test_candidate_display_translates_internal_failure_reason_for_users() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    failed_candidate = summary["algo"]["candidate_comparison"]["candidates"][-1]
    failed_candidate["label"] = "graph_w5_of_5"
    failed_candidate["failure_reason"] = "candidate_time_budget_reached"
    summary["algo"]["candidate_comparison"]["skipped_candidate_labels"] = ["graph_w4_of_5"]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "试算时间到了，系统没有继续算这套方案" in status_text
    assert "重点工序优先方案 5/5" in status_text
    assert "重点工序优先方案 4/5" in status_text
    assert "candidate_time_budget_reached" not in status_text
    assert "graph_w5_of_5" not in status_text
    assert "graph_w4_of_5" not in status_text


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


def test_candidate_display_does_not_duplicate_adopted_plan_suffix() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    candidates = summary["algo"]["candidate_comparison"]["candidates"]
    candidates[0]["label"] = "最终采用方案"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    candidate_labels = [row["candidate_label"] for row in display["rows"]]
    assert "正式采用方案" in candidate_labels
    assert "正式采用方案方案" not in candidate_labels
