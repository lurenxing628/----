"""回归测试：排产手册路由的 src/page 规范化——手册缺失时 full_manual_section_url 归一为空字符串；_normalize_scheduler_manual_args 接受同源绝对 src（保留末尾问号）、对非法 page 返回 None 并给出告警；get_manual_url 与直传 src 都会从返回链接里剥掉未知 plan_role（如 future_role）但保留 version/date_from。"""

from __future__ import annotations

import pytest
from flask import Flask

import web.manual_src_security as manual_src_security_mod
import web.routes.domains.scheduler.scheduler_config as route_mod
import web.ui_mode as ui_mode_mod


def test_get_full_manual_section_url_returns_empty_string_when_manual_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manual_src_security_mod, "build_manual_for_endpoint", lambda *_args, **_kwargs: None)

    assert ui_mode_mod.get_full_manual_section_url(endpoint="scheduler.gantt_page", src="/scheduler/gantt") == ""


def test_build_manual_page_view_state_normalizes_missing_full_manual_section_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(route_mod, "build_page_fallback_text", lambda *_args, **_kwargs: "页面说明")
    monkeypatch.setattr(route_mod, "get_full_manual_section_url", lambda *_args, **_kwargs: None)

    state = route_mod._build_manual_page_view_state(
        raw_page="scheduler.gantt_page",
        bundle={"current_manual": {"title": "甘特图"}, "related_manuals": []},
        manual_text="整本说明",
        link_src="/scheduler/gantt",
        back_url="/scheduler/gantt",
        show_scheduler_nav=True,
    )

    assert state["full_manual_section_url"] == ""


def test_build_related_manual_links_normalizes_missing_full_manual_section_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(route_mod, "_resolve_manual_entry_endpoint", lambda _manual_id: "scheduler.gantt_page")
    monkeypatch.setattr(route_mod, "get_manual_url", lambda *_args, **_kwargs: "/scheduler/config/manual?page=scheduler.gantt_page")
    monkeypatch.setattr(route_mod, "get_full_manual_section_url", lambda *_args, **_kwargs: None)

    related = route_mod._build_related_manual_links(
        [{"manual_id": "scheduler_gantt", "title": "甘特图", "summary": "说明摘要"}],
        "/scheduler/gantt",
    )

    assert related[0]["full_manual_section_url"] == ""


def test_normalize_scheduler_manual_args_accepts_same_origin_absolute_src_and_flags_invalid_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        route_mod,
        "build_page_manual_bundle",
        lambda raw_page: None if raw_page == "bad.page" else {"current_manual": {}, "related_manuals": []},
    )

    app = Flask(__name__)
    with app.test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, bundle, warning = route_mod._normalize_scheduler_manual_args(
            "http://localhost/scheduler/gantt?view=machine",
            "bad.page",
        )

    assert safe_src == "/scheduler/gantt?view=machine"
    assert safe_page is None
    assert bundle is None
    assert "bad.page" in str(warning or "")


def test_get_manual_url_drops_unknown_plan_role_from_return_src(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manual_src_security_mod, "resolve_manual_id", lambda _endpoint: "scheduler_gantt")
    app = Flask(__name__)
    app.add_url_rule(
        "/scheduler/config/manual",
        endpoint="scheduler.config_manual_page",
        view_func=lambda: "",
    )

    with app.test_request_context("/", base_url="http://localhost/"):
        url = manual_src_security_mod.get_manual_url(
            endpoint="scheduler.gantt_page",
            src="/reports/execution-review?version=12&plan_role=future_role&date_from=2026-05-06",
        )

    assert url is not None
    assert "future_role" not in url
    assert "version%3D12" in url
    assert "date_from%3D2026-05-06" in url


def test_manual_page_direct_src_drops_unknown_plan_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        route_mod,
        "build_page_manual_bundle",
        lambda raw_page: {"current_manual": {}, "related_manuals": []},
    )

    app = Flask(__name__)
    with app.test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, bundle, warning = route_mod._normalize_scheduler_manual_args(
            "/reports/execution-review?version=12&plan_role=future_role&date_from=2026-05-06",
            "reports.execution_review_page",
        )

    assert safe_src == "/reports/execution-review?version=12&date_from=2026-05-06"
    assert "future_role" not in str(safe_src)
    assert safe_page == "reports.execution_review_page"
    assert bundle is not None
    assert warning is None


def test_normalize_scheduler_manual_args_preserves_trailing_question_mark_for_same_origin_absolute_src(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        route_mod,
        "build_page_manual_bundle",
        lambda raw_page: {"current_manual": {}, "related_manuals": []},
    )

    app = Flask(__name__)
    with app.test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        safe_src, safe_page, bundle, warning = route_mod._normalize_scheduler_manual_args(
            "http://localhost/scheduler/config?",
            "scheduler.config_page",
        )

    assert safe_src == "/scheduler/config?"
    assert safe_page == "scheduler.config_page"
    assert bundle is not None
    assert warning is None
