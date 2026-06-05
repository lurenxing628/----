from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _load_app_factory(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    db_path = runtime_root / "aps_test.db"
    log_dir = runtime_root / "logs"
    backup_dir = runtime_root / "backups"
    template_dir = runtime_root / "templates_excel"
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(template_dir))

    from core.infrastructure.database import ensure_schema

    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    sys.modules.pop("app", None)
    return importlib.import_module("app").create_app


def test_scheduler_routes_are_registered_by_factory(tmp_path, monkeypatch) -> None:
    create_app = _load_app_factory(tmp_path, monkeypatch)
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/scheduler/run" in rules
    assert "/scheduler/gantt" in rules
    assert "/scheduler/analysis" in rules
    assert "/scheduler/resource-dispatch" in rules
