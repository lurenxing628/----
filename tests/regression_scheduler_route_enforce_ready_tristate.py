import os
import sys
from types import SimpleNamespace
from typing import Any, Dict

from flask import Flask, g
from werkzeug.datastructures import MultiDict


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _invoke_scheduler_run(form_data: Any):
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


def _invoke_scheduler_simulate(form_data: Any):
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


def _assert_form_parser_contract() -> None:
    from core.infrastructure.errors import ValidationError
    from web.routes.form_values import form_optional_toggle_bool, form_toggle_bool, form_yes_no_value

    assert form_yes_no_value(MultiDict([("flag", "yes"), ("flag", "no")]), "flag") == "yes"
    assert form_yes_no_value(MultiDict([("flag", "no"), ("flag", "yes")]), "flag") == "yes"
    assert form_yes_no_value(MultiDict([("flag", "no")]), "flag") == "no"
    assert form_yes_no_value(MultiDict(), "flag", default="no") == "no"
    assert form_yes_no_value({"flag": ["no", "yes"]}, "flag") == "yes"
    try:
        form_yes_no_value(MultiDict([("flag", "maybe")]), "flag", default="yes")
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("字段已提交但取值不认识时，不应静默使用 default")
    try:
        form_toggle_bool(MultiDict([("flag", "maybe")]), "flag", default=False)
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("普通开关收到非法值时，不应静默按 False 处理")
    try:
        form_optional_toggle_bool(MultiDict([("flag", "maybe")]), "flag")
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("可选开关收到非法值时，不应静默按 False 处理")
    assert form_toggle_bool(MultiDict([("flag", "no"), ("flag", "on")]), "flag") is True
    assert form_toggle_bool(MultiDict([("flag", "no")]), "flag", default=True) is False
    assert form_optional_toggle_bool(MultiDict(), "flag") is None
    assert form_optional_toggle_bool(MultiDict([("flag", "no"), ("flag", "on")]), "flag") is True
    assert form_optional_toggle_bool(MultiDict([("flag", "no")]), "flag") is False


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _assert_form_parser_contract()

    # /scheduler/run
    run_default = _invoke_scheduler_run({"batch_ids": ["B001"]})
    assert run_default.get("enforce_ready") is None, f"未传 enforce_ready 时应传递 None：{run_default!r}"
    assert run_default.get("strict_mode") is False, f"未传 strict_mode 时应传递 False：{run_default!r}"

    run_true = _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "on", "strict_mode": "yes"})
    assert run_true.get("enforce_ready") is True, f"勾选 enforce_ready 时应传递 True：{run_true!r}"
    assert run_true.get("strict_mode") is True, f"勾选 strict_mode 时应传递 True：{run_true!r}"

    run_reversed = _invoke_scheduler_run(
        MultiDict(
            [
                ("batch_ids", "B001"),
                ("enforce_ready", "no"),
                ("enforce_ready", "yes"),
                ("strict_mode", "no"),
                ("strict_mode", "on"),
            ]
        )
    )
    assert run_reversed.get("enforce_ready") is True, f"同名 enforce_ready 反序提交应优先识别 yes：{run_reversed!r}"
    assert run_reversed.get("strict_mode") is True, f"同名 strict_mode 反序提交应优先识别 yes：{run_reversed!r}"

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

    sim_reversed = _invoke_scheduler_simulate(
        MultiDict(
            [
                ("batch_ids", "B001"),
                ("enforce_ready", "no"),
                ("enforce_ready", "1"),
                ("strict_mode", "no"),
                ("strict_mode", "yes"),
            ]
        )
    )
    assert sim_reversed.get("enforce_ready") is True, f"simulate 同名 enforce_ready 反序提交应优先识别 yes：{sim_reversed!r}"
    assert sim_reversed.get("strict_mode") is True, f"simulate 同名 strict_mode 反序提交应优先识别 yes：{sim_reversed!r}"

    sim_false = _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "no", "strict_mode": "false"})
    assert sim_false.get("enforce_ready") is False, f"simulate 显式 no 应传递 False：{sim_false!r}"
    assert sim_false.get("strict_mode") is False, f"simulate 显式 false 应传递 False：{sim_false!r}"

    tpl_path = os.path.join(repo_root, "templates", "scheduler", "batches.html")
    run_panel_path = os.path.join(repo_root, "templates", "scheduler", "_run_panel.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    with open(run_panel_path, "r", encoding="utf-8") as f:
        tpl += "\n" + f.read()
    assert "ui.toggle(option.toggle" in tpl, "batches.html 应通过 viewmodel toggle 对象渲染运行选项"
    assert "run_options" in tpl, "batches.html 缺少 run_options 入口"
    assert "发现参数问题就停止排产" in tpl, "batches.html 缺少 strict_mode 文案"

    vm_path = os.path.join(repo_root, "web", "viewmodels", "scheduler_run_options.py")
    with open(vm_path, "r", encoding="utf-8") as f:
        vm_source = f.read()
    assert '"enforce_ready"' in vm_source, "scheduler_batches_page.py 缺少 enforce_ready toggle"
    assert '"strict_mode"' in vm_source, "scheduler_batches_page.py 缺少 strict_mode toggle"

    print("OK")


def test_scheduler_route_enforce_ready_tristate_contract() -> None:
    main()


if __name__ == "__main__":
    main()
