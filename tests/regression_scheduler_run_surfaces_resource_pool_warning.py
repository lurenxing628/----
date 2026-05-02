from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "排产完成（版本 7）" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。" in msg
            for cat, msg in flashes
        ), flashes
        assert any(cat == "warning" and "另有 1 条提醒，请到系统历史查看。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and msg == "第 6 条告警" for cat, msg in flashes), flashes
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
                    "warnings": [
                        "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。",
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "模拟排产完成：生成版本 8" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。" in msg
            for cat, msg in flashes
        ), flashes
        assert any(cat == "warning" and "另有 1 条提醒，请到系统历史查看。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and msg == "第 6 条告警" for cat, msg in flashes), flashes
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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

    duplicate_message = "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert sum(1 for msg in warning_messages if duplicate_message in msg) == 1, warning_messages
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
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
