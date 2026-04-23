from __future__ import annotations

import pytest
from flask import Flask

import web.routes.scheduler_config as route_mod
import web.ui_mode as ui_mode_mod


def test_get_full_manual_section_url_returns_empty_string_when_manual_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_mode_mod, "build_manual_for_endpoint", lambda *_args, **_kwargs: None)

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
