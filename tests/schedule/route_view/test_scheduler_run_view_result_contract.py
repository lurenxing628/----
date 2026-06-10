"""回归测试：build_run_schedule_view_result 与 /scheduler/run 路由的结果分类与脱敏——按 scheduled/total/failed 计数判 success/failed/unknown 不把失败或空结果误判成功，过滤含 Traceback/E_SECRET/私密路径的内部 warning/error 只留口语化公开提示，超期样本至多展示 10 个；路由据此 flash 对应分类、成功/部分跳甘特图版本跨度、坏版本号拦截，ValidationError 类业务错误取 user_message 而意外异常透传到错误边界。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from flask import Flask, g, get_flashed_messages

from core.infrastructure.errors import ValidationError
from tests._support.paths import REPO_ROOT
from web.viewmodels.scheduler_run_view_result import build_run_schedule_view_result


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


def test_run_schedule_view_result_does_not_default_failed_counts_to_success() -> None:
    result = {
        "version": 11,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 0,
            "total_ops": 2,
            "failed_ops": 2,
            "warnings": [],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "failed"
    assert view_result.headline_category == "error"
    assert "排产失败（版本 11）" in view_result.headline_message


def test_run_schedule_view_result_marks_empty_unknown_instead_of_success() -> None:
    result = {
        "version": 11,
        "overdue_batches": [],
        "summary": {
            "warnings": [],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "unknown"
    assert view_result.headline_category == "error"
    assert "排产结果有问题，需要检查（版本 11）" in view_result.headline_message


def test_run_schedule_view_result_respects_explicit_unknown_before_success_counts() -> None:
    result = {
        "version": 11,
        "overdue_batches": [],
        "summary": {
            "completion_status": "unknown",
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "unknown"
    assert view_result.headline_category == "error"
    assert "排产结果有问题，需要检查（版本 11）" in view_result.headline_message


def test_run_schedule_view_result_treats_missing_completion_status_with_errors_as_unknown() -> None:
    result = {
        "version": 11,
        "overdue_batches": [],
        "summary": {
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "error_count": 1,
            "errors": ["Traceback sqlite /tmp/private.db"],
            "warnings": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.result_status == "unknown"
    assert view_result.headline_category == "error"
    assert "排产结果有问题，需要检查（版本 11）" in view_result.headline_message
    assert view_result.error_preview == ["排产执行遇到问题，请联系管理员查看日志。"]


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


def test_run_schedule_view_result_filters_internal_warning_messages() -> None:
    public_warning = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
    result = {
        "version": 14,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [
                "Traceback sqlite raw_internal_warning code=E_SECRET /tmp/private.db",
                public_warning,
            ],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == [public_warning]
    visible = "\n".join(view_result.warning_messages)
    assert "raw_internal_warning" not in visible
    assert "E_SECRET" not in visible
    assert "/tmp/private.db" not in visible
    assert "Traceback" not in visible


def test_run_schedule_view_result_keeps_auto_assign_resource_warning() -> None:
    public_warning = "自动分配已启用，但可用设备或人员资料缺失，自制工序无法自动分配设备或人员。"
    result = {
        "version": 15,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [public_warning],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == [public_warning]


def test_run_schedule_view_result_keeps_public_field_fallback_warnings() -> None:
    public_warnings = [
        "排序策略：部分选项填得不对，本次先按默认值处理。",
        "派工方式：部分必填内容缺失，本次先按默认值处理。",
        "优先级权重：部分数字填得不对，本次先按默认值处理。",
        "就绪权重：部分数字小于允许范围，本次先按默认值处理。",
    ]
    result = {
        "version": 16,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": public_warnings,
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == public_warnings


def test_run_schedule_view_result_rejects_field_warning_with_raw_tail() -> None:
    result = {
        "version": 17,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [
                "排序策略：部分选项填得不对，本次先按默认值处理。 Traceback /tmp/private.db",
                "未知字段：部分选项填得不对，本次先按默认值处理。",
                "派工方式：Traceback raw_internal_warning",
                "排序策略：部分选项填得不对，本次先按默认值处理。",
            ],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == ["排序策略：部分选项填得不对，本次先按默认值处理。"]
    visible = "\n".join(view_result.warning_messages)
    assert "raw_internal_warning" not in visible
    assert "/tmp/private.db" not in visible
    assert "Traceback" not in visible


def test_run_schedule_view_result_rejects_public_warning_prefix_with_raw_tail() -> None:
    safe_start_warning = "开始时间无法解析，本次已改用当前时间。"
    safe_end_warning = "截止日期无法解析，本次已忽略这个截止日期。"
    safe_normalized_warning = "开始时间已规范化为：2026-05-20 08:00:00"
    result = {
        "version": 14,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 1,
            "failed_ops": 0,
            "warnings": [
                "开始时间无法解析，已忽略：'Traceback sqlite raw_internal_warning code=E_SECRET /tmp/private.db'",
                "截止日期无法解析，已忽略：'Traceback sqlite raw_internal_warning code=E_SECRET /tmp/private.db'",
                "开始时间已规范化为：2026-05-20 08:00:00 Traceback sqlite raw_internal_warning",
                safe_start_warning,
                safe_end_warning,
                safe_normalized_warning,
            ],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == [safe_start_warning, safe_end_warning, safe_normalized_warning]
    visible = "\n".join(view_result.warning_messages)
    assert "raw_internal_warning" not in visible
    assert "E_SECRET" not in visible
    assert "/tmp/private.db" not in visible
    assert "Traceback" not in visible


def test_run_schedule_view_result_keeps_unscheduled_batch_warning_without_batch_samples() -> None:
    public_warning = "存在 2 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。"
    result = {
        "version": 18,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 3,
            "failed_ops": 2,
            "warnings": [public_warning],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    assert view_result.warning_messages == [public_warning]


def test_run_schedule_view_result_rejects_unscheduled_batch_warning_with_any_sample_tail() -> None:
    result = {
        "version": 19,
        "overdue_batches": [],
        "summary": {
            "scheduled_ops": 1,
            "total_ops": 3,
            "failed_ops": 2,
            "warnings": [
                "存在 2 个批次未形成完工结果（示例批次：B001、/tmp/private.db SECRET_TOKEN）。",
                "存在 2 个批次未形成完工结果（示例批次：B001、B002）。",
                "存在 2 个批次未形成完工结果（示例批次：secret_token）。",
                "存在 2 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。",
            ],
            "errors": [],
        },
    }

    view_result = build_run_schedule_view_result(result)

    visible = "\n".join(view_result.warning_messages)
    assert view_result.warning_messages == ["存在 2 个批次未形成完工结果，请到系统管理里的排产历史查看这次排产的详细提醒。"]
    assert "/tmp/private.db" not in visible
    assert "SECRET_TOKEN" not in visible
    assert "secret_token" not in visible
    assert "B001" not in visible
    assert "B002" not in visible


def test_scheduler_run_route_flashes_failed_result_and_overdue_sample_limit() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

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


def test_scheduler_run_failed_route_surfaces_sanitized_errors_as_error_flash() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 22,
                "result_status": "failed",
                "overdue_batches": [],
                "summary": {
                    "success": False,
                    "scheduled_ops": 0,
                    "total_ops": 2,
                    "failed_ops": 2,
                    "warnings": [],
                    "errors": ["sqlite OperationalError raw_internal_error code=E_SECRET /tmp/private.db"],
                    "errors_sample": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "error_count": 2,
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-failed-sanitized-errors"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert any(cat == "error" and "排产失败（版本 22）" in msg for cat, msg in flashes), flashes
        assert any(cat == "error" and msg == "排产执行遇到问题，请联系管理员查看日志。" for cat, msg in flashes), flashes
        assert any(cat == "error" and "另有 1 条错误" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "排产执行遇到问题" in msg for cat, msg in flashes), flashes
        visible = "\n".join(msg for _cat, msg in flashes)
        assert "raw_internal_error" not in visible
        assert "E_SECRET" not in visible
        assert "/tmp/private.db" not in visible
        assert "Traceback" not in visible
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_counts_hidden_string_warning_without_leaking_raw_text() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 24,
                "result_status": "success",
                "overdue_batches": [],
                "summary": {
                    "completion_status": "success",
                    "scheduled_ops": 1,
                    "total_ops": 1,
                    "failed_ops": 0,
                    "warnings": "SECRET password raw SQL /tmp/private.db",
                    "errors": [],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-string-warning-hidden-count"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "warning" and "系统记录了 1 条维护诊断" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "另有 1 条提醒" in msg for cat, msg in flashes), flashes
        visible = "\n".join(msg for _cat, msg in flashes)
        assert "SECRET" not in visible
        assert "password" not in visible
        assert "raw SQL" not in visible
        assert "/tmp/private.db" not in visible
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_does_not_count_public_warning_alias_as_hidden() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

    raw_message = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员（请查看日志）。"
    public_message = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 25,
                "result_status": "success",
                "overdue_batches": [],
                "summary": {
                    "completion_status": "success",
                    "scheduled_ops": 1,
                    "total_ops": 1,
                    "failed_ops": 0,
                    "warnings": [raw_message, public_message],
                    "errors": [],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-warning-alias-hidden-count"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert sum(1 for msg in warning_messages if msg == public_message) == 1
        assert not any("另有" in msg for msg in warning_messages), warning_messages
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_unknown_result_stays_on_batches_page_without_success_flash() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 23,
                "overdue_batches": [],
                "summary": {
                    "warnings": [],
                    "errors": [],
                },
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("排产结果有问题时不应该继续读取甘特图范围")

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-run-unknown-status"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService(), gantt_service=_UnexpectedGanttService())
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.headers["Location"] == "/scheduler.batches_page"
        assert any(cat == "error" and "排产结果有问题，需要检查（版本 23）" in msg for cat, msg in flashes), flashes
        assert not any(cat == "success" and "排产完成" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_route_flashes_app_error_user_message() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

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

    import web.routes.domains.scheduler.scheduler_run as route_mod

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
        def resolve_gantt_range_for_version(self, **kwargs):
            version = kwargs.get("version")
            assert int(version) == 31
            return None, {"start_date": "2026-05-11", "end_date": "2026-05-16"}, "version_span"

        def get_version_time_span_dates(self, _version):
            raise AssertionError("成功跳转应通过统一范围入口解析版本跨度")

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
        assert "start_date=" not in location
        assert "end_date=" not in location
        assert any(cat == "success" and "排产完成（版本 31）" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_partial_redirects_to_gantt_with_requested_start_when_span_missing() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    _reset_scheduler_route_modules()

    import web.routes.domains.scheduler.scheduler_run as route_mod

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
        def resolve_gantt_range_for_version(self, **_kwargs):
            return None, None, "request"

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

    import web.routes.domains.scheduler.scheduler_run as route_mod

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

    import web.routes.domains.scheduler.scheduler_run as route_mod

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

    import web.routes.domains.scheduler.scheduler_run as route_mod

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

    import web.routes.domains.scheduler.scheduler_run as route_mod

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
