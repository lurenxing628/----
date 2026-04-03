from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, g, get_flashed_messages

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_run_surfaces_resource_pool_warning() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import web.routes.scheduler_run as route_mod

    class _StubScheduleService:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_schedule(self, **_kwargs):
            return {
                "version": 7,
                "overdue_batches": [],
                "summary": {
                    "scheduled_ops": 1,
                    "total_ops": 1,
                    "failed_ops": 0,
                    "warnings": [
                        "自动分配资源池构建失败，本次排产已降级为不自动分配资源。",
                        "第 2 条告警",
                        "第 3 条告警",
                        "第 4 条告警",
                        "第 5 条告警",
                        "第 6 条告警",
                    ],
                    "errors": [],
                },
            }

    old_service = route_mod.ScheduleService
    old_url_for = route_mod.url_for
    route_mod.ScheduleService = _StubScheduleService
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/run", method="POST", data={"batch_ids": ["B001"]}):
            g.db = object()
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.run_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "排产完成（版本 7）" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "自动分配资源池构建失败，本次排产已降级为不自动分配资源。" in msg
            for cat, msg in flashes
        ), flashes
        assert any(cat == "warning" and "另有 1 条告警，请到系统历史查看。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and msg == "第 6 条告警" for cat, msg in flashes), flashes
    finally:
        route_mod.ScheduleService = old_service
        route_mod.url_for = old_url_for


def test_scheduler_simulate_surfaces_schedule_warnings() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import web.routes.scheduler_week_plan as route_mod

    class _StubScheduleService:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_schedule(self, **_kwargs):
            return {
                "version": 8,
                "summary": {
                    "warnings": [
                        "自动分配资源池构建失败，本次排产已降级为不自动分配资源。",
                        "第 2 条告警",
                        "第 3 条告警",
                        "第 4 条告警",
                        "第 5 条告警",
                        "第 6 条告警",
                    ]
                },
            }

    old_service = route_mod.ScheduleService
    old_url_for = route_mod.url_for
    route_mod.ScheduleService = _StubScheduleService
    route_mod.url_for = lambda endpoint, **_kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/simulate", method="POST", data={"batch_ids": ["B001"]}):
            g.db = object()
            g.app_logger = app.logger
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            flashes = get_flashed_messages(with_categories=True)

        assert getattr(resp, "status_code", 0) in (301, 302)
        assert any(cat == "success" and "模拟排产完成：生成版本 8" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "自动分配资源池构建失败，本次排产已降级为不自动分配资源。" in msg
            for cat, msg in flashes
        ), flashes
        assert any(cat == "warning" and "另有 1 条告警，请到系统历史查看。" in msg for cat, msg in flashes), flashes
        assert not any(cat == "warning" and msg == "第 6 条告警" for cat, msg in flashes), flashes
    finally:
        route_mod.ScheduleService = old_service
        route_mod.url_for = old_url_for
