"""回归测试：开放重定向防护——system_utils._safe_next_url 与 manual_src_security.normalize_manual_src 只接受站内相对路径，拒绝绝对/协议相对/多斜杠/反斜杠/含换行/回车/空字节的 URL，且 scheduler_config._resolve_manual_back_url 仅消费已过滤的 safe_src、对被拒输入折叠为 None。"""

from __future__ import annotations


def _assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{message}: expected={expected!r}, actual={actual!r}")


def _assert_is_none(actual, message: str) -> None:
    if actual is not None:
        raise RuntimeError(f"{message}: expected None, actual={actual!r}")


def test_safe_next_url_hardening(app_client) -> None:
    import importlib

    app = app_client.application

    system_utils = importlib.import_module("web.routes.system_utils")
    manual_src_security = importlib.import_module("web.manual_src_security")
    scheduler_config = importlib.import_module("web.routes.domains.scheduler.scheduler_config")

    with app.test_request_context("/scheduler/config"):
        valid_next_cases = [
            ("/scheduler/config", "/scheduler/config", "keep absolute internal path"),
            ("/scheduler/config?", "/scheduler/config", "trim trailing question mark"),
            ("scheduler/config?", "/scheduler/config", "trim trailing question mark before leading slash"),
            ("/scheduler/config?page=2", "/scheduler/config?page=2", "keep internal query string"),
            ("scheduler/config?page=2", "/scheduler/config?page=2", "add leading slash for bare internal path"),
        ]
        for raw, expected, message in valid_next_cases:
            _assert_equal(system_utils._safe_next_url(raw), expected, message)

        invalid_next_cases = [
            (None, "reject None"),
            ("", "reject empty string"),
            ("   ", "reject whitespace"),
            ("http://evil.example/x", "reject absolute url"),
            ("//evil.example/x", "reject protocol-relative url"),
            ("///evil.example/x", "reject triple-slash url"),
            ("////evil.example/x", "reject quad-slash url"),
            ("\\\\evil.example", "reject leading backslash"),
            ("/\\\\evil.example", "reject embedded backslash"),
            ("/line\nbreak", "reject newline"),
            ("/line\rbreak", "reject carriage return"),
            ("/line\x00break", "reject null byte"),
        ]
        for raw, message in invalid_next_cases:
            _assert_is_none(system_utils._safe_next_url(raw), message)

        valid_src_cases = [
            ("/scheduler/config", "/scheduler/config", "keep manual src path"),
            ("/scheduler/config?", "/scheduler/config?", "preserve trailing question mark in manual src"),
            ("/scheduler/config?page=2", "/scheduler/config?page=2", "keep manual src query string"),
        ]
        for raw, expected, message in valid_src_cases:
            _assert_equal(manual_src_security.normalize_manual_src(raw), expected, message)

        report_src = manual_src_security.normalize_manual_src_context(
            "/reports?version=12&plan_role=adopted&scenario_id=SC-MANUAL"
        )
        assert report_src is not None
        assert "scenario_id=SC-MANUAL" not in report_src
        assert "plan_context_token=" in report_src
        assert "SC-MANUAL" not in report_src

        invalid_src_cases = [
            ("", "reject manual src empty string"),
            ("   ", "reject manual src whitespace"),
            ("scheduler/config", "reject manual src without leading slash"),
            ("http://evil.example/x", "reject manual src absolute url"),
            ("//evil.example/x", "reject manual src protocol-relative url"),
            ("///evil.example/x", "reject manual src triple-slash url"),
            ("////evil.example/x", "reject manual src quad-slash url"),
            ("\\\\evil.example", "reject manual src leading backslash"),
            ("/\\\\evil.example", "reject manual src embedded backslash"),
            ("/line\nbreak", "reject manual src newline"),
            ("/line\rbreak", "reject manual src carriage return"),
            ("/line\x00break", "reject manual src null byte"),
        ]
        for raw, message in invalid_src_cases:
            _assert_is_none(manual_src_security.normalize_manual_src(raw), message)

        safe_src = manual_src_security.normalize_manual_src("/scheduler/config?")
        _assert_equal(
            scheduler_config._resolve_manual_back_url(safe_src),
            "/scheduler/config?",
            "manual back url should consume filtered safe_src only",
        )
        _assert_is_none(
            scheduler_config._resolve_manual_back_url(manual_src_security.normalize_manual_src("http://evil.example/x")),
            "manual back url should stay None for rejected src",
        )
        _assert_is_none(
            scheduler_config._resolve_manual_back_url(None),
            "manual back url should fold empty input to None",
        )


def test_current_public_return_url_drops_internal_plan_identity_fields(app_client) -> None:
    from web.navigation_context import current_public_return_url

    app = app_client.application
    with app.test_request_context(
        "/scheduler/?"
        "status=pending&"
        "candidate_key=SECRET&"
        "selection_candidate_id=11&"
        "resolved_candidate_id=22&"
        "related_op_id=88&"
        "base_plan_role=baseline_best&"
        "candidate_id=33&"
        "source_table=schedule&"
        "source_row_id=44&"
        "op_id=55&"
        "schedule_id=66"
    ):
        public_url = current_public_return_url()

    assert public_url == "/scheduler/?status=pending"
    assert "candidate_key" not in public_url
    assert "selection_candidate_id" not in public_url
    assert "resolved_candidate_id" not in public_url
    assert "related_op_id" not in public_url
    assert "base_plan_role" not in public_url
    assert "candidate_id" not in public_url
    assert "source_table" not in public_url
    assert "source_row_id" not in public_url
    assert "op_id" not in public_url
    assert "schedule_id" not in public_url
