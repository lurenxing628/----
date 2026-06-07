"""守护排产分析页候选方案对比的跳转链接与摘要卡契约：链接随 start_date/end_date 别名透传日期参数、缺日期时禁用并给出含「日期范围」的理由、明细未保存时只隐藏链接；摘要卡固定三种代表角色（正式采用/原算法/重点工序优先）顺序与中文标签、以正式采用方案为唯一对比基准、缺指标显示「暂无数据」不漏 None/nan/null；plan_role 完整性/明细/漂移异常时不展示假链接并给可读 notice。"""

from __future__ import annotations

import json

from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    VALID_PLAN_ROLES,
    SchedulePlanRoleOption,
)
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS
from tests.candidate.test_scheduler_candidate_analysis_contract import (
    _build_app,
    _call_analysis_page,
    _comparison_summary,
    _HistoryServiceStub,
    _plan_role_options,
    _PlanRoleServiceBroken,
    _PlanRoleServiceDetailBroken,
    _PlanRoleServiceDetailBrokenOnResolve,
    _PlanRoleServiceDriftOnResolve,
    _PlanRoleServiceMissingAdopted,
    _PlanRoleServiceMustNotBeCalled,
    _PlanRoleServiceStub,
)


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
