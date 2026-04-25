from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, cast

import pytest
from flask import Flask, g

from web.ui_mode import UI_MODE_COOKIE_KEY


class _Snapshot:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class _ConfigServiceStub:
    def __init__(self) -> None:
        self.snapshot_calls: List[int] = []
        self.backup_calls: List[Dict[str, Any]] = []
        self.logs_calls: List[Dict[str, Any]] = []
        self.set_calls: List[Dict[str, Any]] = []

    def get_snapshot(self, backup_keep_days_default: int):
        self.snapshot_calls.append(int(backup_keep_days_default))
        return _Snapshot(
            auto_backup_enabled="no",
            auto_backup_interval_minutes=60,
            auto_backup_cleanup_enabled="no",
            auto_backup_keep_days=int(backup_keep_days_default),
            auto_backup_cleanup_interval_minutes=1440,
            auto_log_cleanup_enabled="no",
            auto_log_cleanup_keep_days=30,
            auto_log_cleanup_interval_minutes=60,
        )

    def update_backup_settings(self, **kwargs: Any) -> None:
        self.backup_calls.append(dict(kwargs))

    def update_logs_settings(self, **kwargs: Any) -> None:
        self.logs_calls.append(dict(kwargs))

    def set_value(self, config_key: str, value: Any, description: Optional[str] = None) -> None:
        self.set_calls.append(
            {
                "config_key": config_key,
                "value": value,
                "description": description,
            }
        )


class _JobStateItem:
    def __init__(self, *, last_run_time: str, last_run_detail: str) -> None:
        self.last_run_time = last_run_time
        self.last_run_detail = last_run_detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_run_time": self.last_run_time,
            "last_run_detail": self.last_run_detail,
        }


class _JobStateQueryServiceStub:
    def __init__(self) -> None:
        self.queries: List[str] = []
        self.items = {
            "auto_backup": _JobStateItem(last_run_time="2026-01-01 08:00:00", last_run_detail='{"ok": true}'),
            "auto_backup_cleanup": None,
            "auto_log_cleanup": _JobStateItem(last_run_time="bad-time", last_run_detail="{bad json"),
        }

    def get(self, job_key: str):
        self.queries.append(str(job_key))
        return self.items.get(str(job_key))


class _OperationLogItem:
    def __init__(self, *, log_id: int, module: str, detail: str) -> None:
        self.log_id = int(log_id)
        self.module = module
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.log_id,
            "module": self.module,
            "detail": self.detail,
        }


class _OperationLogServiceStub:
    def __init__(self) -> None:
        self.list_calls: List[Dict[str, Any]] = []
        self.delete_one_calls: List[int] = []
        self.delete_many_calls: List[List[int]] = []

    def list_recent(self, **kwargs: Any):
        self.list_calls.append(dict(kwargs))
        return [_OperationLogItem(log_id=1, module="system", detail='{"ok": true}')]

    def delete_by_id(self, log_id: int) -> int:
        self.delete_one_calls.append(int(log_id))
        return 1

    def delete_by_ids(self, log_ids: List[int]) -> int:
        self.delete_many_calls.append([int(x) for x in log_ids])
        return len(log_ids)


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "aps-system-request-services"
    app.config.update(
        {
            "BACKUP_KEEP_DAYS": 9,
            "DATABASE_PATH": "dummy.db",
            "BACKUP_DIR": "dummy_backups",
        }
    )
    return app


def _bind_services(app: Flask, services: Any) -> None:
    g.services = services
    g.app_logger = app.logger
    g.op_logger = None


def test_system_utils_helpers_use_request_services_without_g_db() -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    config_svc = _ConfigServiceStub()
    job_state_svc = _JobStateQueryServiceStub()

    with app.test_request_context("/system/backup"):
        _bind_services(
            app,
            SimpleNamespace(
                system_config_service=config_svc,
                system_job_state_query_service=job_state_svc,
            ),
        )
        snapshot = utils_mod._get_system_cfg_snapshot()
        job_state = utils_mod._get_job_state_map()

    assert snapshot.auto_backup_keep_days == 9
    assert config_svc.snapshot_calls == [9]
    assert job_state_svc.queries == ["auto_backup", "auto_backup_cleanup", "auto_log_cleanup"]
    assert job_state["auto_backup"]["last_run_state"] == "valid"
    assert job_state["auto_backup"]["last_run_detail_obj"] == {"ok": True}
    assert job_state["auto_log_cleanup"]["last_run_state"] == "invalid"
    assert job_state["auto_log_cleanup"]["last_run_detail_obj"] is None


def test_system_utils_request_service_helper_rejects_missing_context_or_service() -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()

    with app.test_request_context("/system/backup"):
        g.app_logger = app.logger
        g.op_logger = None
        with pytest.raises(RuntimeError, match=r"请求上下文缺少 g\.services。"):
            utils_mod._get_request_service("system_config_service")

    with app.test_request_context("/system/backup"):
        _bind_services(app, SimpleNamespace(system_config_service=_ConfigServiceStub()))
        with pytest.raises(RuntimeError, match=r"g\.services 缺少 system_job_state_query_service。"):
            utils_mod._get_system_job_state_query_service()
        with pytest.raises(RuntimeError, match=r"g\.services 缺少 operation_log_service。"):
            utils_mod._get_operation_log_service()


def test_system_history_route_does_not_swallow_missing_request_service() -> None:
    import web.routes.system_history as history_mod

    app = _build_app()

    with app.test_request_context("/system/history"):
        _bind_services(app, SimpleNamespace())
        with pytest.raises(RuntimeError, match=r"g\.services 缺少 schedule_history_query_service。"):
            history_mod.history_page()


def test_system_logs_page_uses_request_services_without_g_db(monkeypatch) -> None:
    import web.routes.system_logs as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = _build_app()
    config_svc = _ConfigServiceStub()
    job_state_svc = _JobStateQueryServiceStub()
    operation_log_svc = _OperationLogServiceStub()

    with app.test_request_context("/system/logs?limit=5&module=system"):
        _bind_services(
            app,
            SimpleNamespace(
                system_config_service=config_svc,
                system_job_state_query_service=job_state_svc,
                operation_log_service=operation_log_svc,
            ),
        )
        payload = cast(Dict[str, Any], route_mod.logs_page())

    assert payload["settings"]["auto_backup_keep_days"] == 9
    assert payload["rows"][0]["id"] == 1
    assert payload["rows"][0]["detail_obj"] == {"ok": True}
    assert operation_log_svc.list_calls == [
        {
            "limit": 5,
            "module": "system",
            "action": None,
            "log_level": None,
            "start_time": None,
            "end_time": None,
        }
    ]


def test_system_logs_page_resolves_chinese_filter_labels_to_raw_codes(monkeypatch) -> None:
    import web.routes.system_logs as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = _build_app()
    operation_log_svc = _OperationLogServiceStub()

    with app.test_request_context("/system/logs?limit=5&module=系统管理&action=备份"):
        _bind_services(
            app,
            SimpleNamespace(
                system_config_service=_ConfigServiceStub(),
                system_job_state_query_service=_JobStateQueryServiceStub(),
                operation_log_service=operation_log_svc,
            ),
        )
        payload = cast(Dict[str, Any], route_mod.logs_page())

    assert operation_log_svc.list_calls[-1]["module"] == "system"
    assert operation_log_svc.list_calls[-1]["action"] == "backup"
    assert payload["filters"]["module"] == "系统管理"
    assert payload["filters"]["module_code"] == "system"
    assert payload["filters"]["action"] == "备份"
    assert payload["filters"]["action_code"] == "backup"
    assert payload["rows"][0]["module"] == "system"
    assert payload["rows"][0]["module_label"] == "系统管理"


def test_system_logs_page_does_not_swallow_missing_request_service(monkeypatch) -> None:
    import web.routes.system_logs as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = _build_app()

    with app.test_request_context("/system/logs?limit=5"):
        _bind_services(
            app,
            SimpleNamespace(
                system_config_service=_ConfigServiceStub(),
                system_job_state_query_service=_JobStateQueryServiceStub(),
            ),
        )
        with pytest.raises(RuntimeError, match=r"g\.services 缺少 operation_log_service。"):
            route_mod.logs_page()


def test_system_backup_and_logs_settings_use_request_services_without_g_db(monkeypatch) -> None:
    import web.routes.system_backup as backup_mod
    import web.routes.system_logs as logs_mod

    monkeypatch.setattr(backup_mod, "url_for", lambda endpoint, **_kwargs: f"/{endpoint}")
    monkeypatch.setattr(logs_mod, "url_for", lambda endpoint, **_kwargs: f"/{endpoint}")

    app = _build_app()
    config_svc = _ConfigServiceStub()
    services = SimpleNamespace(system_config_service=config_svc)

    with app.test_request_context(
        "/system/backup/settings",
        method="POST",
        data={
            "auto_backup_enabled": "yes",
            "auto_backup_interval_minutes": "30",
            "auto_backup_cleanup_enabled": "no",
            "auto_backup_keep_days": "15",
            "auto_backup_cleanup_interval_minutes": "120",
        },
    ):
        _bind_services(app, services)
        response = backup_mod.backup_settings()
        assert response.status_code in (301, 302)

    with app.test_request_context(
        "/system/logs/settings",
        method="POST",
        data={
            "auto_log_cleanup_enabled": "yes",
            "auto_log_cleanup_keep_days": "20",
            "auto_log_cleanup_interval_minutes": "90",
        },
    ):
        _bind_services(app, services)
        response = logs_mod.logs_settings()
        assert response.status_code in (301, 302)

    assert config_svc.backup_calls == [
        {
            "auto_backup_enabled": "yes",
            "auto_backup_interval_minutes": "30",
            "auto_backup_cleanup_enabled": "no",
            "auto_backup_keep_days": "15",
            "auto_backup_cleanup_interval_minutes": "120",
        }
    ]
    assert config_svc.logs_calls == [
        {
            "auto_log_cleanup_enabled": "yes",
            "auto_log_cleanup_keep_days": "20",
            "auto_log_cleanup_interval_minutes": "90",
        }
    ]


def test_system_ui_mode_and_plugin_toggle_use_request_services_without_g_db(monkeypatch) -> None:
    import web.routes.system_plugins as plugins_mod
    import web.routes.system_ui_mode as ui_mode_mod

    monkeypatch.setattr(plugins_mod, "url_for", lambda endpoint, **_kwargs: f"/{endpoint}")

    app = _build_app()
    config_svc = _ConfigServiceStub()
    services = SimpleNamespace(system_config_service=config_svc)

    with app.test_request_context(
        "/system/plugins/toggle",
        method="POST",
        data={"plugin_id": "demo_plugin", "enabled": "on"},
    ):
        _bind_services(app, services)
        response = plugins_mod.plugin_toggle()
        assert response.status_code in (301, 302)

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "/system/backup"},
    ):
        _bind_services(app, services)
        response = ui_mode_mod.ui_mode_set()
        assert response.status_code in (301, 302)
        assert any(f"{UI_MODE_COOKIE_KEY}=v2" in item for item in response.headers.getlist("Set-Cookie"))

    assert config_svc.set_calls == [
        {
            "config_key": "plugin.demo_plugin.enabled",
            "value": "yes",
            "description": None,
        },
        {
            "config_key": "ui_mode",
            "value": "v2",
            "description": "UI 模式：v1/v2（v2=新UI）",
        },
    ]


def test_system_ui_mode_route_does_not_swallow_missing_request_service() -> None:
    import web.routes.system_ui_mode as ui_mode_mod

    app = _build_app()

    with app.test_request_context(
        "/system/ui-mode",
        method="POST",
        data={"mode": "v2", "next": "/system/backup"},
    ):
        g.services = SimpleNamespace()
        g.app_logger = app.logger
        g.op_logger = None
        with pytest.raises(RuntimeError, match=r"g\.services 缺少 system_config_service。"):
            ui_mode_mod.ui_mode_set()
