import os
import sys
from types import SimpleNamespace
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
        def run_schedule(self, **kwargs):
            captured["enforce_ready"] = kwargs.get("enforce_ready")
            captured["strict_mode"] = kwargs.get("strict_mode")
            return {
                "version": 1,
                "summary": {"scheduled_ops": 1, "total_ops": 1, "failed_ops": 0, "warnings": [], "errors": []},
            }

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/run", method="POST", data=form_data):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.run_schedule()
        assert getattr(resp, "status_code", 0) in (301, 302), "run_schedule 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for


def _invoke_scheduler_simulate(form_data: Dict[str, Any]):
    import web.routes.scheduler_week_plan as route_mod

    captured: Dict[str, Any] = {}

    class _StubScheduleService:
        def run_schedule(self, **kwargs):
            captured["enforce_ready"] = kwargs.get("enforce_ready")
            captured["strict_mode"] = kwargs.get("strict_mode")
            return {"version": 1, "summary": {"warnings": []}}

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/simulate", method="POST", data=form_data):
            g.services = SimpleNamespace(schedule_service=_StubScheduleService())
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.simulate_schedule()
        assert getattr(resp, "status_code", 0) in (301, 302), "simulate_schedule 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # /scheduler/run
    run_default = _invoke_scheduler_run({"batch_ids": ["B001"]})
    assert run_default.get("enforce_ready") is None, f"未传 enforce_ready 时应传递 None：{run_default!r}"
    assert run_default.get("strict_mode") is False, f"未传 strict_mode 时应传递 False：{run_default!r}"

    run_true = _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "on", "strict_mode": "yes"})
    assert run_true.get("enforce_ready") is True, f"勾选 enforce_ready 时应传递 True：{run_true!r}"
    assert run_true.get("strict_mode") is True, f"勾选 strict_mode 时应传递 True：{run_true!r}"

    run_false = _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "false", "strict_mode": "no"})
    assert run_false.get("enforce_ready") is False, f"显式 false 应传递 False：{run_false!r}"
    assert run_false.get("strict_mode") is False, f"显式 no 应传递 False：{run_false!r}"

    # /scheduler/simulate
    sim_default = _invoke_scheduler_simulate({"batch_ids": ["B001"]})
    assert sim_default.get("enforce_ready") is None, f"simulate 未传 enforce_ready 时应传递 None：{sim_default!r}"
    assert sim_default.get("strict_mode") is False, f"simulate 未传 strict_mode 时应传递 False：{sim_default!r}"

    sim_true = _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "1", "strict_mode": "on"})
    assert sim_true.get("enforce_ready") is True, f"simulate 勾选 enforce_ready 时应传递 True：{sim_true!r}"
    assert sim_true.get("strict_mode") is True, f"simulate 勾选 strict_mode 时应传递 True：{sim_true!r}"

    sim_false = _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "no", "strict_mode": "false"})
    assert sim_false.get("enforce_ready") is False, f"simulate 显式 no 应传递 False：{sim_false!r}"
    assert sim_false.get("strict_mode") is False, f"simulate 显式 false 应传递 False：{sim_false!r}"

    tpl_path = os.path.join(repo_root, "templates", "scheduler", "batches.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    assert 'name="strict_mode"' in tpl, "batches.html 缺少 strict_mode 入口"
    assert "发现参数问题就停止排产" in tpl, "batches.html 缺少 strict_mode 文案"

    print("OK")


if __name__ == "__main__":
    main()
