from __future__ import annotations

import importlib
from pathlib import Path

from core.infrastructure.database import ensure_schema
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import field_label_for

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_error_field_label.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_error_page_uses_registry_field_label(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)

    @app.get("/__boom_validation_error")
    def _boom():
        raise ValidationError("bad objective", field="objective")

    resp = app.test_client().get("/__boom_validation_error")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert field_label_for("objective") in body
    assert "field_zh" not in body
