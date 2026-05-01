from __future__ import annotations

import importlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import field_label_for
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _build_real_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema

    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)

    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _mutate_real_scheduler_config(db_path: str, *, delete_keys=()) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        for key in list(delete_keys or []):
            conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (str(key),))
        conn.commit()
    finally:
        conn.close()


class _AttrDict(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


class _ConfigServiceStub:
    def __init__(self) -> None:
        self.restore_default_called = False
        self.save_page_config_called = False
        self.saved_payload = None
        self.mark_active_preset_custom_called = False
        self.snapshot = _AttrDict(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            ready_weight=0.1,
            holiday_default_efficiency=0.8,
            enforce_ready_default="no",
            prefer_primary_skill="no",
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            auto_assign_enabled="no",
            auto_assign_persist="yes",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="greedy",
            time_budget_seconds=20,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=3,
            degradation_events=(),
        )
        self.apply_result = {
            "requested_preset": "默认-稳定",
            "effective_active_preset": "默认-稳定",
            "status": "applied",
            "adjusted_fields": [],
            "reason": None,
            "error_field": None,
            "error_fields": [],
            "error_message": None,
        }
        self.save_result = {
            "requested_preset": "测试方案",
            "effective_active_preset": "测试方案",
            "status": "saved",
            "adjusted_fields": [],
            "reason": None,
            "error_field": None,
            "error_fields": [],
            "error_message": None,
        }
        self.save_outcome = SimpleNamespace(
            visible_changed_fields=["sort_strategy"],
            visible_repaired_fields=[],
            hidden_repaired_fields=[],
            blocked_hidden_repairs=[],
            notices=[],
            meta_parse_warnings=[],
            active_preset_after="custom",
            active_preset_reason_after="manual",
        )

    def get_snapshot(self, *, strict_mode=False):
        return self.snapshot

    def get_available_strategies(self):
        return ["priority_first", "due_date_first"]

    def get_page_metadata(self, _keys):
        return {}

    def list_presets(self):
        return ["默认-稳定"]

    def get_active_preset(self):
        return "默认-稳定"

    def get_active_preset_reason(self):
        return "当前以手动设置为准。"

    def get_preset_display_state(self, readonly=True, current_snapshot=None):
        snapshot = current_snapshot or self.snapshot
        degraded = bool(tuple(getattr(snapshot, "degradation_events", ()) or ()))
        return {
            "presets": [{"name": "默认-稳定"}],
            "active_preset": "默认-稳定",
            "active_preset_reason": "当前以手动设置为准。",
            "active_preset_missing": False,
            "active_preset_reason_missing": False,
            "current_config_state": {
                "state": "degraded" if degraded else "custom",
                "status_label": "存在兼容修补" if degraded else "手动设置",
                "label": "当前运行配置存在兼容修补，不能视为与“默认-稳定”完全一致；请保存后修复。" if degraded else "当前以手动设置为准。",
                "baseline_label": "默认-稳定",
                "baseline_source": "builtin",
                "baseline_key": "默认-稳定",
                "is_custom": False,
                "is_builtin": True,
                "degraded": degraded,
                "provenance_missing": False,
                "active_preset_missing": False,
                "active_preset_reason_missing": False,
                "reason": "当前以手动设置为准。",
                "repair_notice": {"kind": "none", "fields": [], "message": None},
            },
            "readonly": bool(readonly),
        }

    def restore_default(self) -> None:
        self.restore_default_called = True

    def mark_active_preset_custom(self) -> None:
        self.mark_active_preset_custom_called = True

    def save_page_config(self, payload):
        self.save_page_config_called = True
        self.saved_payload = dict(payload or {})
        return self.save_outcome

    def apply_preset(self, _name):
        return dict(self.apply_result)

    def save_preset(self, _name):
        return dict(self.save_result)


def _build_app(monkeypatch, config_service: _ConfigServiceStub) -> Flask:
    import web.routes.scheduler_config as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-config-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(config_service=config_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_config_route_uses_request_services(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    get_response = client.get("/scheduler/config")
    payload = get_response.get_json()

    assert get_response.status_code == 200
    assert payload["builtin_presets"]
    assert payload["current_config_state"]["baseline_label"] == "默认-稳定"
    assert payload["current_config_state"]["state"] == "custom"
    assert payload["current_config_state"]["baseline_source"] == "builtin"
    assert payload["current_config_state"]["degraded"] is False
    assert payload["current_config_state"]["label"] == "当前以手动设置为准。"
    assert payload["auto_assign_persist_state"]["enabled"] is True
    assert payload["auto_assign_persist_state"]["label"]

    post_response = client.post("/scheduler/config/default")

    assert post_response.status_code in (301, 302)
    assert config_service.restore_default_called is True


def test_scheduler_config_post_uses_atomic_save_entrypoint(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config",
        data={
            "sort_strategy": "weighted",
            "priority_weight": "0.4",
            "due_weight": "0.5",
            "holiday_default_efficiency": "0.8",
            "prefer_primary_skill": "yes",
            "enforce_ready_default": "no",
            "dispatch_mode": "sgs",
            "dispatch_rule": "cr",
            "auto_assign_enabled": "yes",
            "ortools_enabled": "no",
            "ortools_time_limit_seconds": "5",
            "algo_mode": "improve",
            "objective": "min_tardiness",
            "time_budget_seconds": "30",
            "freeze_window_enabled": "yes",
            "freeze_window_days": "2",
        },
    )

    assert response.status_code in (301, 302)
    assert config_service.save_page_config_called is True
    assert config_service.saved_payload["dispatch_mode"] == "sgs"
    assert config_service.saved_payload["priority_weight"] == "0.4"


def test_scheduler_config_post_only_passes_explicitly_submitted_fields(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config",
        data={
            "sort_strategy": "priority_first",
            "priority_weight": "0.4",
            "due_weight": "0.5",
        },
    )

    assert response.status_code in (301, 302)
    assert config_service.save_page_config_called is True
    assert "sort_strategy" in config_service.saved_payload
    assert "priority_weight" in config_service.saved_payload
    assert "due_weight" in config_service.saved_payload
    assert "holiday_default_efficiency" not in config_service.saved_payload
    assert "dispatch_mode" not in config_service.saved_payload


def test_scheduler_config_post_surfaces_hidden_repair_notice(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_outcome = SimpleNamespace(
        visible_changed_fields=[],
        visible_repaired_fields=[],
        hidden_repaired_fields=["auto_assign_persist"],
        blocked_hidden_repairs=[],
        notices=[
            {
                "kind": "hidden",
                "fields": ["auto_assign_persist"],
                "message": "\u517c\u5bb9\u4fee\u8865\u5df2\u56de\u5199\u9690\u85cf\u914d\u7f6e\u9879\uff1aauto_assign_persist\u3002",
            }
        ],
        active_preset_after="legacy-demo",
        active_preset_reason_after="hidden",
    )
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post("/scheduler/config", data={"sort_strategy": "priority_first"})

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    warning_messages = [str(message) for category, message in flashes if category == "warning"]
    assert any("自动分配结果回写" in message for message in warning_messages), flashes
    assert not any("保存为自定义配置" in message for message in warning_messages), flashes
    assert not any("auto_assign_persist" in message for message in warning_messages), flashes
    assert not any(category == "success" and "\u5df2\u4fdd\u5b58" in str(message) for category, message in flashes), flashes


def test_scheduler_config_visible_degradation_warning_hides_raw_event_message() -> None:
    from web.routes.domains.scheduler.scheduler_config_display_state import (
        build_config_degraded_display_state,
        get_scheduler_visible_config_field_metadata,
    )

    cfg = SimpleNamespace(
        sort_strategy="priority_first",
        degradation_events=(
            {
                "code": "invalid_choice",
                "field": "sort_strategy",
                "message": "sort_strategy 取值不合法（当前值：'SECRET_BAD_MODE'，允许值：priority_first），已按兼容读取回退。",
                "sample": "SECRET_BAD_MODE",
            },
        ),
    )

    warnings, degraded_fields, hidden_warnings = build_config_degraded_display_state(
        cfg,
        config_field_metadata=get_scheduler_visible_config_field_metadata(),
    )

    rendered = str(warnings.get("sort_strategy") or "")
    assert degraded_fields == ["sort_strategy"]
    assert hidden_warnings == []
    assert "排产策略" in rendered
    assert "当前配置无效" in rendered
    assert "priority_first" not in rendered
    assert "SECRET_BAD_MODE" not in rendered
    assert "sort_strategy" not in rendered


def test_scheduler_config_post_surfaces_blocked_hidden_repair_notice(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_outcome = SimpleNamespace(
        visible_changed_fields=[],
        visible_repaired_fields=[],
        hidden_repaired_fields=[],
        blocked_hidden_repairs=["auto_assign_persist"],
        notices=[
            {
                "kind": "blocked_hidden",
                "fields": ["auto_assign_persist"],
                "message": "\u68c0\u6d4b\u5230\u9690\u85cf\u914d\u7f6e\u9000\u5316\uff0c\u4f46\u56e0\u6765\u6e90\u7f3a\u5931\u672a\u81ea\u52a8\u4fee\u590d\uff1aauto_assign_persist\u3002",
            }
        ],
        active_preset_after=None,
        active_preset_reason_after=None,
    )
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post("/scheduler/config", data={"sort_strategy": "priority_first"})

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "warning" and "\u6765\u6e90\u7f3a\u5931" in str(message) for category, message in flashes), flashes
    assert not any(category == "warning" and "auto_assign_persist" in str(message) for category, message in flashes), flashes
    assert not any(category == "success" and "\u5df2\u4fdd\u5b58" in str(message) for category, message in flashes), flashes


def test_scheduler_config_post_mixed_visible_change_and_blocked_hidden_repair_does_not_flash_success(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_outcome = SimpleNamespace(
        visible_changed_fields=["sort_strategy"],
        visible_repaired_fields=[],
        hidden_repaired_fields=[],
        blocked_hidden_repairs=["auto_assign_persist"],
        notices=[
            {
                "kind": "blocked_hidden",
                "fields": ["auto_assign_persist"],
                "message": "检测到隐藏配置退化，但因来源缺失未自动修复：auto_assign_persist。",
            }
        ],
        active_preset_after="custom",
        active_preset_reason_after="manual",
    )
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post("/scheduler/config", data={"sort_strategy": "weighted"})

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "warning" and "来源缺失" in str(message) for category, message in flashes), flashes
    assert not any(category == "success" for category, _message in flashes), flashes
    assert "auto_assign_persist" not in str(flashes)


def test_scheduler_config_post_surfaces_active_preset_meta_parse_warning(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_outcome = SimpleNamespace(
        visible_changed_fields=[],
        visible_repaired_fields=[],
        hidden_repaired_fields=[],
        blocked_hidden_repairs=[],
        notices=[],
        meta_parse_warnings=[
            {
                "field": "active_preset_meta",
                "message": "active_preset_meta 不是有效 JSON，已按历史来源信息继续显示。",
            }
        ],
        active_preset_after="custom",
        active_preset_reason_after="manual",
    )
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post("/scheduler/config", data={"sort_strategy": "priority_first"})

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "warning" and "方案来源记录" in str(message) for category, message in flashes), flashes
    assert not any(category == "warning" and "active_preset_meta" in str(message) for category, message in flashes), flashes


def test_scheduler_config_post_visible_repair_marks_custom_provenance(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        config_service = ConfigService(conn, logger=None, op_logger=None)
        config_service.restore_default()
        saved = config_service.save_preset("legacy-demo")
        assert saved["effective_active_preset"] == "legacy-demo"

        with config_service.tx_manager.transaction():
            config_service.repo.set(
                "holiday_default_efficiency",
                "NaN",
                description=config_service._field_description("holiday_default_efficiency"),
            )

        app = _build_app(monkeypatch, config_service)
        client = app.test_client()

        response = client.post(
            "/scheduler/config",
            data={
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            },
            follow_redirects=True,
        )

        payload = response.get_json()
        assert response.status_code == 200
        assert payload["active_preset"] == config_service.ACTIVE_PRESET_CUSTOM
        assert payload["current_config_state"]["state"] == "custom"
        assert payload["current_config_state"]["reason"] == config_service.ACTIVE_PRESET_REASON_VISIBLE_REPAIR
    finally:
        conn.close()


def test_scheduler_config_post_surfaces_service_validation_message(monkeypatch) -> None:
    config_service = _ConfigServiceStub()

    def _raise(_payload) -> None:
        raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")

    config_service.save_page_config = _raise
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config",
        data={
            "sort_strategy": "weighted",
            "priority_weight": "40",
            "due_weight": "0.5",
            "holiday_default_efficiency": "0.8",
            "prefer_primary_skill": "no",
            "enforce_ready_default": "no",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "slack",
            "auto_assign_enabled": "no",
            "ortools_enabled": "no",
            "ortools_time_limit_seconds": "5",
            "algo_mode": "greedy",
            "objective": "min_overdue",
            "time_budget_seconds": "20",
            "freeze_window_enabled": "no",
            "freeze_window_days": "3",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any("权重输入疑似混用小数与百分比" in str(message) for _category, message in flashes), flashes


def test_scheduler_config_route_separates_saved_preset_and_runtime_state(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.snapshot.degradation_events = (
        {
            "code": "invalid_choice",
            "scope": "scheduler.config_snapshot",
            "field": "auto_assign_persist",
            "message": "auto_assign_persist defaulted to yes",
        },
    )
    config_service.get_active_preset_reason = lambda: None
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.get("/scheduler/config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["current_config_state"]["baseline_label"] == "默认-稳定"
    assert payload["current_config_state"]["state"] == "degraded"
    assert payload["current_config_state"]["degraded"] is True
    assert "不能视为与“默认-稳定”完全一致" in payload["current_config_state"]["label"]
    assert payload["config_hidden_warnings"]


def test_scheduler_config_legacy_wrapper_loads_only_scheduler_config_leaf() -> None:
    code = """
import importlib
import json
import sys

route_mod = importlib.import_module("web.routes.scheduler_config")
print(json.dumps({
    "module": route_mod.__name__,
    "loaded_pages": "web.routes.domains.scheduler.scheduler_pages" in sys.modules,
    "loaded_registrar": "web.routes.domains.scheduler.scheduler_route_registrar" in sys.modules,
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["module"] == "web.routes.domains.scheduler.scheduler_config"
    assert payload["loaded_pages"] is False
    assert payload["loaded_registrar"] is False


def test_scheduler_config_preset_apply_uses_effective_identity_in_flash(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.apply_result = {
        "requested_preset": "旧方案",
        "effective_active_preset": "旧方案",
        "status": "adjusted",
        "adjusted_fields": ["auto_assign_persist"],
        "reason": "方案应用时发生规范化或修补，当前运行配置与所选方案存在差异。",
        "error_field": None,
        "error_message": None,
    }
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/apply",
        data={"preset_name": "旧方案"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any("当前运行配置已被规范化" in str(message) for _category, message in flashes), flashes
    assert any("旧方案" in str(message) for _category, message in flashes), flashes


def test_scheduler_config_preset_apply_adjusted_flash_hides_unknown_raw_field(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.apply_result = {
        "requested_preset": "旧方案",
        "effective_active_preset": "旧方案",
        "status": "adjusted",
        "adjusted_fields": ["legacy_runtime_block", "legacyRuntimeBlock", "secret", "auto_assign_persist"],
        "reason": "方案应用时发生规范化或修补，当前运行配置与所选方案存在差异。",
        "error_field": None,
        "error_message": None,
    }
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/apply",
        data={"preset_name": "旧方案"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    text = str(flashes)
    assert "当前运行配置已被规范化" in text
    assert "legacy_runtime_block" not in text
    assert "legacyRuntimeBlock" not in text
    assert "secret" not in text
    assert "auto_assign_persist" not in text
    assert "隐藏配置" in text


def test_scheduler_config_preset_apply_surfaces_rejected_validation_failure(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.apply_result = {
        "requested_preset": "缺省字段方案",
        "effective_active_preset": "默认-稳定",
        "status": "rejected",
        "adjusted_fields": [],
        "reason": None,
        "error_field": "priority_weight",
        "error_fields": ["priority_weight", "due_weight"],
        "error_message": "方案缺少必填字段：priority_weight、due_weight。",
    }
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/apply",
        data={"preset_name": "缺省字段方案"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any("当前方案未应用" in str(message) for _category, message in flashes), flashes
    assert any(field_label_for("priority_weight") in str(message) for _category, message in flashes), flashes
    assert any(field_label_for("due_weight") in str(message) for _category, message in flashes), flashes
    assert not any("priority_weight" in str(message) or "due_weight" in str(message) for _category, message in flashes), flashes


def test_scheduler_config_multi_field_error_flash_keeps_full_message() -> None:
    import web.routes.scheduler_config as route_mod

    text = route_mod._format_preset_error_flash(
        error_field="priority_weight",
        error_fields=["priority_weight", "due_weight"],
        error_message="当前方案未应用。 方案缺少必填字段：priority_weight、due_weight。",
    )

    assert field_label_for("priority_weight") in text
    assert field_label_for("due_weight") in text
    assert "priority_weight" not in text and "due_weight" not in text
    assert text != f"{field_label_for('priority_weight')}：当前方案未应用。 方案缺少必填字段：、due_weight。"


def test_scheduler_config_preset_save_surfaces_rejected_strict_error(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_result = {
        "requested_preset": "脏方案",
        "effective_active_preset": "默认-稳定",
        "status": "rejected",
        "adjusted_fields": [],
        "reason": None,
        "error_field": "auto_assign_persist",
        "error_message": "auto_assign_persist 非法，当前配置未保存为方案。",
    }
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/save",
        data={"preset_name": "脏方案"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any("当前配置未保存为方案" in str(message) for _category, message in flashes), flashes
    assert any(field_label_for("auto_assign_persist") in str(message) for _category, message in flashes), flashes
    assert not any("auto_assign_persist" in str(message) for _category, message in flashes), flashes


def test_scheduler_config_preset_save_surfaces_field_label_even_without_raw_key(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.save_result = {
        "requested_preset": "脏方案",
        "effective_active_preset": "默认-稳定",
        "status": "rejected",
        "adjusted_fields": [],
        "reason": None,
        "error_field": "auto_assign_persist",
        "error_message": "当前配置未保存为方案。",
    }
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/save",
        data={"preset_name": "脏方案"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any("当前配置未保存为方案" in str(message) for _category, message in flashes), flashes
    assert any(field_label_for("auto_assign_persist") in str(message) for _category, message in flashes), flashes


def test_scheduler_config_preset_delete_missing_does_not_flash_success(monkeypatch) -> None:
    from core.infrastructure.errors import BusinessError, ErrorCode

    config_service = _ConfigServiceStub()

    def _raise_missing(_name) -> None:
        raise BusinessError(ErrorCode.NOT_FOUND, "未找到方案：missing-demo")

    config_service.delete_preset = _raise_missing
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/config/preset/delete",
        data={"preset_name": "missing-demo"},
        follow_redirects=False,
    )

    assert response.status_code in (301, 302)
    with client.session_transaction() as session:
        flashes = list(session.get("_flashes") or [])
    assert any(category == "error" and "未找到方案" in str(message) for category, message in flashes), flashes
    assert not any(category == "success" for category, _message in flashes), flashes


def test_scheduler_config_page_exposes_hidden_degraded_warning_summary(monkeypatch) -> None:
    config_service = _ConfigServiceStub()
    config_service.snapshot.degradation_events = (
        {
            "code": "invalid_choice",
            "scope": "scheduler.config_snapshot",
            "field": "auto_assign_persist",
            "message": "字段“auto_assign_persist”取值不合法，已按兼容读取回退为 yes。",
            "count": 1,
        },
    )
    app = _build_app(monkeypatch, config_service)
    client = app.test_client()

    response = client.get("/scheduler/config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["config_hidden_warnings"]
    hidden_text = "\n".join(str(item) for item in payload["config_hidden_warnings"])
    assert "自动分配结果回写" in hidden_text
    assert "auto_assign_persist" not in hidden_text
    assert "yes" not in hidden_text


def test_scheduler_config_get_keeps_missing_objective_and_provenance_readonly(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        config_service = ConfigService(conn, logger=None, op_logger=None)
        config_service.restore_default()
        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
            ("objective", config_service.ACTIVE_PRESET_KEY, config_service.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()

        app = _build_app(monkeypatch, config_service)
        client = app.test_client()

        first_payload = client.get("/scheduler/config").get_json()
        second_payload = client.get("/scheduler/config").get_json()

        remaining = {
            row["config_key"]
            for row in conn.execute(
                "SELECT config_key FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
                ("objective", config_service.ACTIVE_PRESET_KEY, config_service.ACTIVE_PRESET_REASON_KEY),
            ).fetchall()
        }
        assert remaining == set(), remaining
        assert "objective" in list(first_payload["config_degraded_fields"] or [])
        assert first_payload["current_config_state"]["degraded"] is True
        assert first_payload["current_config_state"]["provenance_missing"] is True
        assert first_payload["current_config_state"]["baseline_source"] == "unknown"
        assert first_payload["current_config_state"]["baseline_label"] == "基线未记录"
        assert second_payload["current_config_state"]["degraded"] is True
        assert second_payload["current_config_state"]["provenance_missing"] is True
        assert list(second_payload["config_degraded_fields"] or []) == list(first_payload["config_degraded_fields"] or [])
    finally:
        conn.close()


def test_scheduler_config_get_keeps_hidden_only_missing_field_readonly(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        config_service = ConfigService(conn, logger=None, op_logger=None)
        config_service.restore_default()
        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", ("auto_assign_persist",))
        conn.commit()

        app = _build_app(monkeypatch, config_service)
        client = app.test_client()

        first_payload = client.get("/scheduler/config").get_json()
        second_payload = client.get("/scheduler/config").get_json()

        count_after = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("auto_assign_persist",),
        ).fetchone()[0]
        assert int(count_after or 0) == 0
        assert first_payload["current_config_state"]["degraded"] is True
        assert first_payload["config_hidden_warnings"]
        assert second_payload["current_config_state"]["degraded"] is True
        assert second_payload["config_hidden_warnings"]
    finally:
        conn.close()


def test_scheduler_config_get_marks_named_baseline_drift_not_exact(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        config_service = ConfigService(conn, logger=None, op_logger=None)
        config_service.restore_default()
        saved = config_service.save_preset("route-drift-demo")
        assert saved["effective_active_preset"] == "route-drift-demo"

        drifted_payload = config_service.get_snapshot(strict_mode=True).to_dict()
        drifted_payload["sort_strategy"] = "due_date_first"
        with config_service.tx_manager.transaction():
            config_service.repo.set(
                config_service._preset_key("route-drift-demo"),
                json.dumps(drifted_payload, ensure_ascii=False, sort_keys=True),
                description="drifted route preset payload",
            )

        app = _build_app(monkeypatch, config_service)
        client = app.test_client()

        payload = client.get("/scheduler/config").get_json()

        assert payload["active_preset"] == "route-drift-demo"
        assert payload["current_config_state"]["state"] == "adjusted"
        assert payload["current_config_state"]["baseline_source"] == "named"
        assert payload["current_config_state"]["provenance_missing"] is False
    finally:
        conn.close()


def test_scheduler_config_page_renders_provenance_and_hidden_degraded_html(tmp_path, monkeypatch) -> None:
    app, db_path = _build_real_app(tmp_path, monkeypatch)
    _mutate_real_scheduler_config(
        db_path,
        delete_keys=(
            "objective",
            ConfigService.ACTIVE_PRESET_KEY,
            ConfigService.ACTIVE_PRESET_REASON_KEY,
            "auto_assign_persist",
        ),
    )
    client = app.test_client()

    response = client.get("/scheduler/config")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "常用方案" in body
    assert "基线未记录" in body
    assert "当前运行配置缺少基线记录，无法确认与任何方案的一致性；请显式保存或重新应用方案。" in body
    assert "当前配置中有" in body
    assert "使用了兼容显示值，请保存后修复。" in body
    assert "当前还有内部配置项存在兼容修补：" in body
    assert "自动分配结果回写" in body
    assert "auto_assign_persist" not in body


def test_scheduler_config_legacy_wrapper_uses_domain_registrar_source_of_truth() -> None:
    source = (REPO_ROOT / "web/routes/scheduler_config.py").read_text(encoding="utf-8")

    assert "load_scheduler_route_module" in source
    assert "scheduler" in source
    assert ".domains.scheduler.scheduler_analysis" not in source
