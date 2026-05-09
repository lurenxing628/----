import os
import sys
from io import BytesIO
from types import SimpleNamespace
from typing import Any, Dict

from flask import Flask, g, get_flashed_messages
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
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.run_schedule()
            captured["flashes"] = get_flashed_messages(with_categories=True)
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
            g.services = SimpleNamespace(
                schedule_service=_StubScheduleService(),
                gantt_service=SimpleNamespace(get_version_time_span_dates=lambda _version: None),
            )
            g.app_logger = None
            g.op_logger = None
            resp = route_mod.simulate_schedule()
            captured["flashes"] = get_flashed_messages(with_categories=True)
        assert getattr(resp, "status_code", 0) in (301, 302), "simulate_schedule 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for


def _invoke_system_plugin_toggle(form_data: Any):
    import web.routes.system_plugins as route_mod

    captured: Dict[str, Any] = {}

    class _StubConfigService:
        def set_value(self, key, value, description=None):
            captured["key"] = key
            captured["value"] = value
            captured["description"] = description

    old_url_for = route_mod.url_for
    old_get_svc = route_mod._get_system_config_service
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    route_mod._get_system_config_service = lambda: _StubConfigService()
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/system/plugins/toggle", method="POST", data=form_data):
            g.op_logger = None
            resp = route_mod.plugin_toggle()
        assert getattr(resp, "status_code", 0) in (301, 302), "plugin_toggle 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for
        route_mod._get_system_config_service = old_get_svc


def _invoke_system_backup_settings(form_data: Any):
    import web.routes.system_backup as route_mod

    captured: Dict[str, Any] = {}

    class _StubConfigService:
        def update_backup_settings(self, **kwargs):
            captured.update(kwargs)

    old_url_for = route_mod.url_for
    old_get_svc = route_mod._get_system_config_service
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    route_mod._get_system_config_service = lambda: _StubConfigService()
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/system/backup/settings", method="POST", data=form_data):
            resp = route_mod.backup_settings()
            captured["flashes"] = get_flashed_messages(with_categories=True)
        assert getattr(resp, "status_code", 0) in (301, 302), "backup_settings 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for
        route_mod._get_system_config_service = old_get_svc


def _invoke_system_logs_settings(form_data: Any):
    import web.routes.system_logs as route_mod

    captured: Dict[str, Any] = {}

    class _StubConfigService:
        def update_logs_settings(self, **kwargs):
            captured.update(kwargs)

    old_url_for = route_mod.url_for
    old_get_svc = route_mod._get_system_config_service
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    route_mod._get_system_config_service = lambda: _StubConfigService()
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/system/logs/settings", method="POST", data=form_data):
            resp = route_mod.logs_settings()
            captured["flashes"] = get_flashed_messages(with_categories=True)
        assert getattr(resp, "status_code", 0) in (301, 302), "logs_settings 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for
        route_mod._get_system_config_service = old_get_svc


def _invoke_process_create_part(form_data: Any):
    import web.routes.process_parts as route_mod

    captured: Dict[str, Any] = {}

    class _StubPart:
        part_no = "P001"
        part_name = "测试件"

    class _StubPartService:
        def __init__(self, *args, **kwargs):
            pass

        def create(self, **kwargs):
            captured["strict_mode"] = kwargs.get("strict_mode")
            return _StubPart()

    old_url_for = route_mod.url_for
    old_part_service = route_mod.PartService
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    route_mod.PartService = _StubPartService
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/process/parts/create", method="POST", data=form_data):
            g.db = object()
            g.op_logger = None
            resp = route_mod.create_part()
        assert getattr(resp, "status_code", 0) in (301, 302), "create_part 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for
        route_mod.PartService = old_part_service


def _invoke_scheduler_create_batch(form_data: Any):
    import web.routes.domains.scheduler.scheduler_batches as route_mod

    captured: Dict[str, Any] = {}

    class _StubBatch:
        batch_id = "B001"

    class _StubBatchService:
        def create_batch_from_template(self, **kwargs):
            captured["strict_mode"] = kwargs.get("strict_mode")
            return _StubBatch()

        def list_operations(self, batch_id):
            return []

        def consume_user_visible_warnings(self):
            return []

    old_url_for = route_mod.url_for
    route_mod.url_for = lambda endpoint, **kwargs: f"/{endpoint}"
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context("/scheduler/batches/create", method="POST", data=form_data):
            g.services = SimpleNamespace(batch_service=_StubBatchService())
            resp = route_mod.create_batch()
        assert getattr(resp, "status_code", 0) in (301, 302), "create_batch 应返回 redirect"
        return dict(captured)
    finally:
        route_mod.url_for = old_url_for


def _invoke_scheduler_excel_batches_preview(form_data: Any):
    import web.routes.domains.scheduler.scheduler_excel_batches as route_mod

    captured: Dict[str, Any] = {}

    old_read_uploaded = route_mod._read_uploaded_xlsx
    old_ensure_unique = route_mod._ensure_unique_ids
    old_parse_mode = route_mod._parse_mode
    old_baseline_extra_state = route_mod._batch_baseline_extra_state

    def _stop_after_toggle(*args, **kwargs):
        captured["auto_generate_ops"] = kwargs.get("auto_generate_ops")
        captured["strict_mode"] = kwargs.get("strict_mode")
        raise RuntimeError("stop after toggle parse")

    route_mod._read_uploaded_xlsx = lambda file: [{"批次号": "B001"}]
    route_mod._ensure_unique_ids = lambda *args, **kwargs: None
    route_mod._parse_mode = lambda raw: SimpleNamespace(value=str(raw or "overwrite"))
    route_mod._batch_baseline_extra_state = _stop_after_toggle
    try:
        app = Flask(__name__)
        app.secret_key = "aps-test-secret"
        with app.test_request_context(
            "/scheduler/excel/batches/preview",
            method="POST",
            data=form_data,
            content_type="multipart/form-data",
        ):
            g.services = SimpleNamespace(
                batch_service=SimpleNamespace(list=lambda: []),
                part_service=SimpleNamespace(list=lambda: []),
                part_operation_query_service=object(),
                excel_service=SimpleNamespace(preview_import=lambda **kwargs: []),
            )
            g.op_logger = None
            try:
                route_mod.excel_batches_preview()
            except RuntimeError as exc:
                assert str(exc) == "stop after toggle parse"
        return dict(captured)
    finally:
        route_mod._read_uploaded_xlsx = old_read_uploaded
        route_mod._ensure_unique_ids = old_ensure_unique
        route_mod._parse_mode = old_parse_mode
        route_mod._batch_baseline_extra_state = old_baseline_extra_state


def _assert_form_parser_contract() -> None:
    from core.infrastructure.errors import ValidationError
    from web.routes.form_values import form_optional_toggle_bool, form_toggle_bool, form_yes_no_value

    assert form_yes_no_value(MultiDict([("flag", "yes"), ("flag", "no")]), "flag") == "yes"
    assert form_yes_no_value(MultiDict([("flag", "no"), ("flag", "yes")]), "flag") == "yes"
    assert form_yes_no_value(MultiDict([("flag", "no")]), "flag") == "no"
    assert form_yes_no_value(MultiDict(), "flag", default="no") == "no"
    assert form_yes_no_value({"flag": ["no", "yes"]}, "flag") == "yes"
    assert form_yes_no_value({"flag": 0}, "flag") == "no"
    assert form_yes_no_value({"flag": False}, "flag") == "no"
    assert form_yes_no_value({"flag": [0]}, "flag") == "no"
    assert form_yes_no_value({"flag": [False]}, "flag") == "no"
    assert form_toggle_bool({"flag": 0}, "flag") is False
    assert form_toggle_bool({"flag": False}, "flag") is False
    try:
        form_yes_no_value(MultiDict([("flag", "maybe")]), "flag", default="yes")
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("字段已提交但取值不认识时，不应静默使用 default")
    for bad_values in (
        [("flag", "yes"), ("flag", "maybe")],
        [("flag", "no"), ("flag", "maybe")],
        [("flag", "maybe"), ("flag", "yes")],
    ):
        try:
            form_yes_no_value(MultiDict(bad_values), "flag")
        except ValidationError as exc:
            assert "flag 取值不合法" in exc.message
        else:
            raise AssertionError(f"混入非法值时不应静默挑选合法值：{bad_values!r}")
    try:
        form_toggle_bool(MultiDict([("flag", "maybe")]), "flag", default=False)
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("普通开关收到非法值时，不应静默按 False 处理")
    try:
        form_toggle_bool(MultiDict([("flag", "no"), ("flag", "maybe")]), "flag", default=False)
    except ValidationError as exc:
        assert "flag 取值不合法" in exc.message
    else:
        raise AssertionError("普通开关混入非法值时，不应静默按合法 no 处理")
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


def _assert_toggle_validation_flash(result: Dict[str, Any], *, field_name: str) -> None:
    assert len(result) == 1 and "flashes" in result, f"非法 {field_name} 不应继续调用服务：{result!r}"
    flashes = result["flashes"]
    assert flashes, f"非法 {field_name} 应给用户闪现错误提示"
    assert flashes[0][0] == "error", flashes
    assert f"{field_name} 取值不合法" in flashes[0][1] or "参数填写不正确" in flashes[0][1], flashes


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
    _assert_toggle_validation_flash(
        _invoke_scheduler_run({"batch_ids": ["B001"], "enforce_ready": "maybe", "strict_mode": "no"}),
        field_name="enforce_ready",
    )
    _assert_toggle_validation_flash(
        _invoke_scheduler_run({"batch_ids": ["B001"], "strict_mode": "maybe"}),
        field_name="strict_mode",
    )

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
    _assert_toggle_validation_flash(
        _invoke_scheduler_simulate({"batch_ids": ["B001"], "enforce_ready": "maybe", "strict_mode": "no"}),
        field_name="enforce_ready",
    )
    _assert_toggle_validation_flash(
        _invoke_scheduler_simulate({"batch_ids": ["B001"], "strict_mode": "maybe"}),
        field_name="strict_mode",
    )

    plugin_on = _invoke_system_plugin_toggle(
        MultiDict([("plugin_id", "demo"), ("enabled", "no"), ("enabled", "yes")])
    )
    assert plugin_on.get("value") == "yes", f"插件开关同名反序提交应识别 yes：{plugin_on!r}"
    plugin_off = _invoke_system_plugin_toggle({"plugin_id": "demo"})
    assert plugin_off.get("value") == "no", f"插件开关未提交 enabled 时应按 no 保存：{plugin_off!r}"
    plugin_invalid = _invoke_system_plugin_toggle({"plugin_id": "demo", "enabled": "maybe"})
    assert "value" not in plugin_invalid, f"插件开关非法值不应静默保存：{plugin_invalid!r}"

    backup_invalid = _invoke_system_backup_settings(
        {"auto_backup_enabled": "maybe", "auto_backup_cleanup_enabled": "no"}
    )
    _assert_toggle_validation_flash(backup_invalid, field_name="auto_backup_enabled")
    logs_invalid = _invoke_system_logs_settings({"auto_log_cleanup_enabled": "maybe"})
    _assert_toggle_validation_flash(logs_invalid, field_name="auto_log_cleanup_enabled")

    process_create = _invoke_process_create_part(
        MultiDict([("part_no", "P001"), ("part_name", "测试件"), ("strict_mode", "no"), ("strict_mode", "yes")])
    )
    assert process_create.get("strict_mode") is True, f"工艺新增 strict_mode 反序提交应识别 yes：{process_create!r}"

    batch_create = _invoke_scheduler_create_batch(
        MultiDict([("batch_id", "B001"), ("part_no", "P001"), ("quantity", "1"), ("strict_mode", "no"), ("strict_mode", "yes")])
    )
    assert batch_create.get("strict_mode") is True, f"批次新增 strict_mode 反序提交应识别 yes：{batch_create!r}"

    batch_excel_preview = _invoke_scheduler_excel_batches_preview(
        MultiDict(
            [
                ("mode", "overwrite"),
                ("auto_generate_ops", "0"),
                ("auto_generate_ops", "1"),
                ("strict_mode", "no"),
                ("strict_mode", "yes"),
                ("file", (BytesIO(b"fake xlsx bytes"), "batches.xlsx")),
            ]
        )
    )
    assert batch_excel_preview.get("auto_generate_ops") is True, f"批次 Excel 自动生成工序反序提交应识别 yes：{batch_excel_preview!r}"
    assert batch_excel_preview.get("strict_mode") is True, f"批次 Excel strict_mode 反序提交应识别 yes：{batch_excel_preview!r}"

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
