from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import current_app, g

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
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

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_request_scope_app_logger_binding(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)

    import web.routes.scheduler_batches as route_mod

    captured = {}

    class _StubBatchService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            captured["logger"] = logger
            captured["op_logger"] = op_logger

        def list(self, status=None):
            captured["status"] = status
            return []

    class _StubConfigService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            captured["config_logger"] = logger
            captured["config_op_logger"] = op_logger

        def get_snapshot(self):
            return SimpleNamespace(enforce_ready_default="no")

        def get_available_strategies(self):
            return []

        def list_presets(self):
            return []

        def get_active_preset(self):
            return None

    class _StubHistoryService:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_recent(self, limit=1):
            return []

    monkeypatch.setattr(route_mod, "BatchService", _StubBatchService)
    monkeypatch.setattr(route_mod, "ConfigService", _StubConfigService)
    monkeypatch.setattr(route_mod, "ScheduleHistoryQueryService", _StubHistoryService)
    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    with app.test_request_context("/scheduler/"):
        app.preprocess_request()

        assert g.app_logger is current_app.logger
        assert getattr(g, "db", None) is not None
        assert getattr(g, "op_logger", None) is not None

        route_mod.batches_page()

        assert captured.get("logger") is current_app.logger
        assert captured.get("config_logger") is current_app.logger
        assert captured.get("op_logger") is g.op_logger
        assert captured.get("config_op_logger") is g.op_logger
