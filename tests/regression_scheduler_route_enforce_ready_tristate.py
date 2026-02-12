import os
import sys
from typing import Any, Dict

from flask import Flask, g


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _invoke_scheduler_run(form_data: Dict[str, Any]):
    import web.routes.scheduler_run as route_mod

    captured: Dict[str, Any] = {}

    class _StubScheduleService:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_schedule(self, **kwargs):
            captured["enforce_ready"] = kwargs.get("enforce_ready")
            return {
                "version": 1,
                "summary": {"scheduled_ops": 1, "total_ops": 1, "failed_ops": 0, "warnings": [], "errors": []},
            }

    old_svc = route_mod.ScheduleService
    old_url_for = route_mod.url_for
    route_mod.ScheduleService = _StubScheduleService
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/run", method="POST", data=form_data):
            g.db = object()
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.run_schedule()
        assert getattr(resp, "status_code", 0) in (301, 302), "run_schedule 应返回 redirect"
        return captured.get("enforce_ready")
    finally:
        route_mod.ScheduleService = old_svc
        route_mod.url_for = old_url_for


def _invoke_scheduler_simulate(form_data: Dict[str, Any]):
    import web.routes.scheduler_week_plan as route_mod

    captured: Dict[str, Any] = {}

    class _StubScheduleService:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_schedule(self, **kwargs):
            captured["enforce_ready"] = kwargs.get("enforce_ready")
            return {"version": 1, "summary": {"warnings": []}}

    old_svc = route_mod.ScheduleService
    old_url_for = route_mod.url_for
    route_mod.ScheduleService = _StubScheduleService
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/simulate", method="POST", data=form_data):
            g.db = object()
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.simulate_schedule()
        assert getattr(resp, "status_code", 0) in (301, 302), "simulate_schedule 应返回 redirect"
        return captured.get("enforce_ready")
    finally:
        route_mod.ScheduleService = old_svc
        route_mod.url_for = old_url_for


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # /scheduler/run
    assert _invoke_scheduler_run({"batch_ids": ["B001"]}) is None, "未传 enforce_ready 时应传递 None"
    assert _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "on"}) is True, "勾选时应传递 True"
    assert _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "false"}) is False, "显式 false 应传递 False"

    # /scheduler/simulate
    assert _invoke_scheduler_simulate({"batch_ids": ["B001"]}) is None, "simulate 未传 enforce_ready 时应传递 None"
    assert _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "1"}) is True, "simulate 勾选时应传递 True"
    assert _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "no"}) is False, "simulate 显式 no 应传递 False"

    print("OK")


if __name__ == "__main__":
    main()
