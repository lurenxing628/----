"""回归测试：/scheduler/run 与 /scheduler/simulate 路由把 run_schedule 的 summary 翻译成给用户看的 flash——首两条降级/规范化告警原样透出、其余折叠为「系统记录了 N 条维护诊断」；partial/failed/unknown/缺版本号等非成功结果不闪 success 且不跳甘特图（停在批次页），错误明细脱敏（不泄露 Traceback/raw_internal_error/E_SECRET/私有路径），并对主次降级消息去重。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from flask import Flask, g, get_flashed_messages

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_scheduler_route_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)


def test_scheduler_run_surfaces_resource_pool_warning() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 7,
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 1,
                    "failed_ops": 0,
                    "warnings": [
                        "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。",
                        "开始时间已规范化为：2026-05-20 08:00:00",
                        "第 2 条告警",
                        "第 3 条告警",
                        "第 4 条告警",
                        "第 5 条告警",
                        "第 6 条告警",
                    ],
                    "errors": [],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "排产完成（版本 7）" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "开始时间已规范化为：2026-05-20 08:00:00" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "系统记录了 5 条维护诊断" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "另有 5 条提醒" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "第 " in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_surfaces_schedule_warnings() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 8,
                "summary": {
                    "completion_status": "success",
                    "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
                    "warnings": [
                        "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。",
                        "截止日期无法解析，本次已忽略这个截止日期。",
                        "第 2 条告警",
                        "第 3 条告警",
                        "第 4 条告警",
                        "第 5 条告警",
                        "第 6 条告警",
                    ]
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "模拟排产完成：生成版本 8" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "截止日期无法解析，本次已忽略这个截止日期。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "第 " in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_redirects_to_generated_schedule_start_range() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 18,
                "summary": {
                    "completion_status": "success",
                    "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
                    "start_time": "2026-05-04 08:00:00",
                    "warnings": [],
                },
            }

    captured = {}
    old_url_for = route_mod.url_for

    def _fake_url_for(endpoint, **kwargs):
        captured["endpoint"] = endpoint
        captured["kwargs"] = dict(kwargs)
        return f"/{endpoint}?{urlencode(kwargs)}"

    route_mod.url_for = _fake_url_for
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-gantt-redirect"
        with app.test_request_context(
            "/scheduler/simulate",
            method="POST",
            data={"batch_ids": ["B001"], "start_dt": "2026-06-01T08:00"},
        ):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert captured.get("endpoint") == "scheduler.gantt_page"
        kwargs = captured.get("kwargs") or {}
        assert kwargs.get("view") == "machine"
        assert kwargs.get("start_date") == "2026-05-04"
        assert kwargs.get("end_date") == "2026-05-10"
        assert kwargs.get("version") == 18
        assert "week_start" not in kwargs
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_with_execution_facts_does_not_redirect_to_missing_version() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "is_simulation": True,
                "version": None,
                "result_persisted": False,
                "can_open_result_version": False,
                "user_message": "现场已经有开工或完工记录，这次模拟只做安全检查，没有生成新的排程版本，也没有改动正式排程。",
                "result_status": "simulated",
                "summary": {
                    "completion_status": "success",
                    "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
                    "warnings": [],
                },
            }

    captured = []
    old_url_for = route_mod.url_for

    def _fake_url_for(endpoint, **kwargs):
        captured.append((endpoint, dict(kwargs)))
        return f"/{endpoint}?{urlencode(kwargs)}"

    route_mod.url_for = _fake_url_for
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-execution-facts"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert captured[-1][0] == "scheduler.batches_page"
        assert not any(endpoint == "scheduler.gantt_page" for endpoint, _kwargs in captured)
        assert any(cat == "warning" and "没有生成新的排程版本" in msg for cat, msg in flashes), flashes
        assert not any("生成版本" in msg for _cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_failed_result_stays_on_batches_page() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 40,
                "result_status": "simulated",
                "summary": {
                    "completion_status": "failed",
                    "warnings": [],
                    "errors": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "errors_sample": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "error_count": 2,
                    "counts": {"op_count": 1, "scheduled_ops": 0, "failed_ops": 1},
                },
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("失败的模拟排产不应该跳去甘特图")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-failed-stays-on-batches"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and "模拟排产失败：生成版本 40" in msg for cat, msg in flashes), flashes
        assert any(cat == "error" and msg == "排产执行遇到问题，请联系管理员查看日志。" for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "排产执行遇到问题" in msg for cat, msg in flashes), flashes
        visible = "\n".join(msg for _cat, msg in flashes)
        assert "raw_internal_error" not in visible
        assert "E_SECRET" not in visible
        assert "/tmp/private.db" not in visible
        assert "Traceback" not in visible
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_unknown_result_stays_on_batches_page() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 41,
                "result_status": "simulated",
                "summary": {
                    "warnings": [],
                    "errors": [],
                },
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("结果有问题的模拟排产不应该跳去甘特图")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-unknown-stays-on-batches"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and "模拟排产结果有问题，需要检查：生成版本 41" in msg for cat, msg in flashes), flashes
        assert not any(cat == "success" and "模拟排产完成" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


@pytest.mark.parametrize(
    "raw_summary",
    [
        "Traceback sqlite /tmp/private.db secret",
        ["Traceback", "/tmp/private.db", "secret"],
    ],
)
def test_scheduler_simulate_non_dict_summary_does_not_crash_or_leak(raw_summary) -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 51,
                "result_status": "simulated",
                "summary": raw_summary,
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("非 dict summary 不应该导致误跳甘特图")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-non-dict-summary"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and "模拟排产结果有问题，需要检查：生成版本 51" in msg for cat, msg in flashes), flashes
        assert not any(cat == "success" and "模拟排产完成" in msg for cat, msg in flashes), flashes
        visible = "\n".join(msg for _cat, msg in flashes)
        assert "Traceback" not in visible
        assert "/tmp/private.db" not in visible
        assert "secret" not in visible.lower()
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_missing_completion_status_with_errors_stays_on_batches_page() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 52,
                "result_status": "simulated",
                "summary": {
                    "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
                    "errors": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "error_count": 1,
                    "warnings": [],
                },
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("缺完成状态但有错误的模拟排产不应该跳去甘特图")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-missing-status-errors"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and "模拟排产结果有问题，需要检查：生成版本 52" in msg for cat, msg in flashes), flashes
        assert any(cat == "error" and msg == "排产执行遇到问题，请联系管理员查看日志。" for cat, msg in flashes), flashes
        assert not any(cat == "success" and "模拟排产完成" in msg for cat, msg in flashes), flashes
        visible = "\n".join(msg for _cat, msg in flashes)
        assert "raw_internal_error" not in visible
        assert "E_SECRET" not in visible
        assert "/tmp/private.db" not in visible
        assert "Traceback" not in visible
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_explicit_unknown_with_success_counts_stays_on_batches_page() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 42,
                "result_status": "simulated",
                "summary": {
                    "completion_status": "unknown",
                    "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
                    "errors": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "errors_sample": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
                    "error_count": 1,
                    "warnings": [],
                },
            }

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("显式问题状态不应该跳去甘特图")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-explicit-unknown"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and "模拟排产结果有问题，需要检查：生成版本 42" in msg for cat, msg in flashes), flashes
        assert any(cat == "error" and msg == "排产执行遇到问题，请联系管理员查看日志。" for cat, msg in flashes), flashes
        assert not any(cat == "success" and "模拟排产完成" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


@pytest.mark.parametrize(
    "result, expected_message",
    [
        ({"summary": {}}, "排产结果缺少可查看的版本号"),
        ({"version": 0, "summary": {}}, "排产版本"),
        ({"version": "abc", "summary": {}}, "排产版本"),
    ],
)
def test_scheduler_simulate_requires_valid_version_before_completion_flash(result, expected_message: str) -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return result

    class _UnexpectedGanttService:
        def get_version_time_span_dates(self, _version):
            raise AssertionError("版本号无效时不应该查询甘特图范围")

    captured_endpoints = []
    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: captured_endpoints.append(endpoint) or f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-invalid-version"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=_UnexpectedGanttService(),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert resp.location == "/scheduler.batches_page"
        assert "scheduler.gantt_page" not in captured_endpoints
        assert any(cat == "error" and expected_message in msg for cat, msg in flashes), flashes
        assert not any("模拟排产完成" in msg or "模拟排产失败" in msg for _cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_partial_result_is_not_flashed_as_success() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 9,
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

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-partial-status"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "warning" and "部分" in msg for cat, msg in flashes), flashes
        assert not any(cat == "success" for cat, _msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_partial_result_still_surfaces_primary_degradation() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 10,
                "result_status": "partial",
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 2,
                    "failed_ops": 1,
                    "warnings": [],
                    "errors": [],
                    "degraded_causes": ["resource_pool_degraded"],
                    "degradation_events": [
                        {
                            "code": "resource_pool_degraded",
                            "message": "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。",
                            "count": 1,
                        }
                    ],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-partial-degraded-status"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "warning" and "排产部分完成" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "本次排产部分完成，并且有些数据或设置需要复核，系统先按能确认的内容继续。" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "资源池资料不完整" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "resource_pool_degraded" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_flashes_secondary_degradation_messages_without_warning_duplicates() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    duplicate_message = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员（请查看日志）。"
    public_duplicate_message = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
    distinct_message = "冻结窗口资料不完整，本次只保留能确认的冻结工序。"

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 11,
                "result_status": "partial",
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 2,
                    "failed_ops": 1,
                    "warnings": [duplicate_message],
                    "errors": [],
                    "degradation_events": [
                        {"code": "resource_pool_degraded", "message": duplicate_message, "count": 1},
                        {"code": "freeze_window_degraded", "message": distinct_message, "count": 1},
                    ],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secondary-degradation"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert sum(1 for msg in warning_messages if public_duplicate_message in msg) == 1, warning_messages
        assert not any(duplicate_message in msg for msg in warning_messages), warning_messages
        assert sum(1 for msg in warning_messages if distinct_message in msg) == 1, warning_messages
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_dedupes_secondary_messages_already_summarized_by_primary() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 11,
                "result_status": "partial",
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 2,
                    "failed_ops": 1,
                    "warnings": [],
                    "errors": [],
                    "degradation_events": [
                        {"code": "freeze_window_degraded", "message": "", "count": 1},
                    ],
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secondary-primary-dedupe"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert len(warning_messages) == 2, warning_messages
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_surfaces_canonical_summary_errors() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 11,
                "result_status": "partial",
                "summary": {
                    "success": False,
                    "total_ops": 2,
                    "scheduled_ops": 1,
                    "failed_ops": 1,
                    "warnings": [],
                    "errors": ["输入窗口冲突", "资源池为空"],
                    "error_count": 4,
                    "errors_sample": ["输入窗口冲突", "资源池为空"],
                    "degradation_events": [],
                    "degradation_counters": {},
                    "degraded_success": False,
                    "degraded_causes": [],
                    "counts": {
                        "op_count": 2,
                        "total_ops": 2,
                        "scheduled_ops": 1,
                        "failed_ops": 1,
                    },
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulate-errors"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "warning" and "部分完成" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "排产执行遇到问题，请联系管理员查看日志。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "输入窗口冲突" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "资源池为空" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "另有 3 条错误" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_run_surfaces_summary_display_errors_preview() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 12,
                "result_status": "partial",
                "overdue_batches": [],
                "summary": {
                    "success": False,
                    "total_ops": 3,
                    "scheduled_ops": 1,
                    "failed_ops": 2,
                    "warnings": [],
                    "errors": [],
                    "error_count": 4,
                    "errors_sample": ["输入窗口冲突", "资源池为空"],
                    "degradation_events": [],
                    "degradation_counters": {},
                    "degraded_success": False,
                    "degraded_causes": [],
                    "counts": {
                        "op_count": 3,
                        "total_ops": 3,
                        "scheduled_ops": 1,
                        "failed_ops": 2,
                    },
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-run-errors-preview"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "warning" and "部分" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "排产执行遇到问题，请联系管理员查看日志。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "输入窗口冲突" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and "资源池为空" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "另有 3 条错误" in msg for cat, msg in flashes), flashes
    finally:
        route_mod.url_for = old_url_for


def test_scheduler_simulate_uses_simulated_degradation_message_without_duplicate_counted_reason() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _reset_scheduler_route_modules()

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def run_schedule(self, **_kwargs):
            return {
                "version": 13,
                "result_status": "simulated",
                "summary": {
                    "warnings": [],
                    "errors": [],
                    "degradation_events": [
                        {"code": "resource_pool_degraded", "message": "", "count": 2},
                    ],
                    "counts": {
                        "op_count": 1,
                        "scheduled_ops": 1,
                        "failed_ops": 0,
                    },
                },
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-simulated-degradation-message"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "\u6a21\u62df\u6392\u4ea7\u5b8c\u6210" in msg for cat, msg in flashes), flashes
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert any("\u6a21\u62df\u6392\u4ea7" in msg for msg in warning_messages), warning_messages
        assert not any("\u672c\u6b21\u6392\u4ea7\u5df2\u6210\u529f" in msg for msg in warning_messages), warning_messages
        assert sum(1 for msg in warning_messages if "\u8d44\u6e90\u6c60\u8d44\u6599\u4e0d\u5b8c\u6574\uff082\uff09" in msg) == 1, warning_messages
    finally:
        route_mod.url_for = old_url_for
