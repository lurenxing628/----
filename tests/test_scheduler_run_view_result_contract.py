from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from flask import Flask, g, get_flashed_messages

from core.infrastructure.errors import ValidationError
from web.viewmodels.scheduler_run_view_result import build_run_schedule_view_result

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_scheduler_route_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)


def test_run_schedule_view_result_builds_success_headline_without_overdue() -> None:
    result = {
        "version": 11,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "success"
    assert view_result.headline_category == "success"
    assert view_result.headline_message == "排产完成（版本 11）：成功 1/1，失败 0。无超期。"
    assert view_result.overdue_sample == ()
    assert view_result.overdue_sample_message is None


def test_run_schedule_view_result_builds_failed_headline_and_overdue_sample() -> None:
    result = {
        "version": 12,
        "result_status": "failed",
        "overdue_batches": [{"batch_id": f"B{i:03d}"} for i in range(1, 13)],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 3,
            "failed_ops": 2,
            "warnings": [],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "failed"
    assert view_result.headline_category == "error"
    assert "排产失败（版本 12）" in view_result.headline_message
    assert "成功 1/3，失败 2。超期 12 个。" in view_result.headline_message
    assert view_result.overdue_sample == tuple(f"B{i:03d}" for i in range(1, 11))
    assert view_result.overdue_sample_message == "超期批次（最多展示10个）：B001，B002，B003，B004，B005，B006，B007，B008，B009，B010"


def test_run_schedule_view_result_surfaces_public_degradation_warning_and_errors() -> None:
    duplicate_warning = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
    result = {
        "version": 13,
        "result_status": "partial",
        "overdue_batches": [],
        "summary": {
            "success": False,
            "scheduled_ops": 1,
            "total_ops": 2,
            "failed_ops": 1,
            "warnings": [duplicate_warning],
            "errors_sample": ["输入窗口冲突", "资源池为空"],
            "error_count": 4,
            "degraded_causes": ["resource_pool_degraded"],
            "degradation_events": [
                {
                    "code": "resource_pool_degraded",
                    "message": duplicate_warning,
                    "count": 1,
                }
            ],
            "counts": {
                "op_count": 2,
                "total_ops": 2,
                "scheduled_ops": 1,
                "failed_ops": 1,
            },
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.headline_category == "warning"
    assert view_result.primary_degradation_message is not None
    assert "本次排产部分完成" in view_result.primary_degradation_message
    assert "资源池资料不完整" in view_result.primary_degradation_message
    assert "resource_pool_degraded" not in view_result.primary_degradation_message
    assert view_result.warning_messages == [duplicate_warning]
    assert view_result.error_preview == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert view_result.error_total == 4


def test_scheduler_run_route_does_not_parse_display_state_inline() -> None:
    route_source = (REPO_ROOT / "web/routes/domains/scheduler/scheduler_run.py").read_text(encoding="utf-8")
    run_body = route_source.split("def run_schedule():", 1)[1]

    assert "build_summary_display_state" not in run_body
    assert "summary_display" not in run_body
    assert 'result.get("summary")' not in run_body
    assert 'result.get("overdue_batches")' not in run_body
    assert "overdue_batches" not in run_body


def test_scheduler_run_route_flashes_failed_result_and_overdue_sample_limit() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 21,
                "result_status": "failed",
                "overdue_batches": [{"batch_id": f"B{i:03d}"} for i in range(1, 13)],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 3,
                    "failed_ops": 2,
                    "warnings": [],
                    "errors": [],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-failed-overdue"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert any(
            cat == "error" and "排产失败（版本 21）：成功 1/3，失败 2。超期 12 个。" in msg
            for cat, msg in flashes
        ), flashes
        assert any(
            cat == "warning"
            and msg == "超期批次（最多展示10个）：B001，B002，B003，B004，B005，B006，B007，B008，B009，B010"
            for cat, msg in flashes
        ), flashes
        assert not any("B011" in msg or "B012" in msg for _cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_flashes_app_error_user_message() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            raise ValidationError("所选批次没有可重排工序，本次未执行排产。", field="排产")

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-app-error"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert [msg for cat, msg in flashes if cat == "error"] == ["所选批次没有可重排工序，本次未执行排产。"]
        assert not any("排产完成" in msg for _cat, msg in flashes), flashes
        assert not any("[1001]" in msg or "ValidationError" in msg or "field" in msg for _cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_success_redirects_to_gantt_actual_span() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 31,
                "result_status": "success",
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 2,
                    "total_ops": 2,
                    "failed_ops": 0,
                    "warnings": [],
                    "errors": [],
                },
            }

    class _StubGanttService:
        def get_version_time_span_dates(self, version):
            assert int(version) == 31
            return {"start_date": "2026-05-11", "end_date": "2026-05-16"}

    old_url_for = route_mod.url_for

    def _fake_url_for(endpoint, **kwargs):
        return f"/{endpoint}?{urlencode(kwargs)}"

    route_mod.url_for = _fake_url_for
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-run-success-gantt-redirect"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService(), gantt_service=_StubGanttService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        location = resp.headers["Location"]
        assert location.startswith("/scheduler.gantt_page?")
        assert "view=machine" in location
        assert "version=31" in location
        assert "start_date=2026-05-11" in location
        assert "end_date=2026-05-16" in location
        assert any(cat == "success" and "排产完成（版本 31）" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_partial_redirects_to_gantt_with_requested_start_when_span_missing() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 32,
                "result_status": "partial",
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 2,
                    "failed_ops": 1,
                    "warnings": [],
                    "errors": [],
                },
            }

    class _StubGanttService:
        def get_version_time_span_dates(self, _version):
            return None

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}?{urlencode(kwargs)}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-run-partial-gantt-redirect"
        with app.test_request_context(
            "/scheduler/run",
            method="POST",
            data={"batch_ids": ["B001"], "start_dt": "2026/06/01 09:00:00"},
        ):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService(), gantt_service=_StubGanttService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        location = resp.headers["Location"]
        assert "scheduler.gantt_page" in location
        assert "view=machine" in location
        assert "version=32" in location
        assert "start_date=2026-06-01" in location
        assert "end_date=2026-06-07" in location
        assert any(cat == "warning" and "部分" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


@pytest.mark.parametrize(
    ("result_status", "include_version", "bad_version", "expected_error"),
    [
        ("success", False, None, "排产结果缺少可查看的版本号"),
        ("success", True, "", "排产版本"),
        ("success", True, 0, "排产版本"),
        ("success", True, "abc", "排产版本"),
        ("partial", False, None, "排产结果缺少可查看的版本号"),
        ("partial", True, "", "排产版本"),
        ("partial", True, 0, "排产版本"),
        ("partial", True, "abc", "排产版本"),
    ],
)
def test_scheduler_run_success_or_partial_requires_valid_version_before_success_flash(
    result_status: str,
    include_version: bool,
    bad_version,
    expected_error: str,
) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            result = {
                "result_status": result_status,
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 1,
                    "failed_ops": 0,
                    "warnings": [],
                    "errors": [],
                },
            }
            if include_version:
                result["version"] = bad_version
            return result

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("坏版本号不应继续读取甘特图范围")

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-run-invalid-version"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService(), gantt_service=_UnexpectedGanttService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert any(cat == "error" and expected_error in msg for cat, msg in flashes), flashes
        assert not any(cat in ("success", "warning") and ("排产完成" in msg or "部分完成" in msg) for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_flashes_ready_error_without_generic_boundary() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            raise ValidationError("以下批次未齐套，禁止排产：B-NO-001", field="齐套")

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-ready-error"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B-NO-001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert [msg for cat, msg in flashes if cat == "error"] == ["以下批次未齐套，禁止排产：B-NO-001"]
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_flashes_missing_resource_user_message() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            exc = ValidationError("优化结果未生成有效可落库排程行", field="schedule")
            exc.details = dict(exc.details or {})
            exc.details["reason"] = "no_actionable_schedule_rows"
            exc.details["user_message"] = (
                "本次排产没有生成可保存结果，存在内部工序缺设备/人员："
                "B-MISS-001 / 工序10 / 粗车 缺设备、人员。请先到批次工序补充页补齐后重试。"
            )
            raise exc

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-missing-resource-error"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B-MISS-001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        error_messages = [msg for cat, msg in flashes if cat == "error"]
        assert len(error_messages) == 1
        assert "B-MISS-001 / 工序10 / 粗车 缺设备、人员" in error_messages[0]
        assert "优化结果未生成有效可落库排程行" not in error_messages[0]
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_lets_unexpected_error_reach_error_boundary() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            raise RuntimeError("database password leaked")

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-unexpected-error"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            with pytest.raises(RuntimeError, match="database password leaked"):
                route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert flashes == []
    finally:
        route_mod.url_for = old_url_for
