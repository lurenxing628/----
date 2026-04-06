from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

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
    return app_mod.create_app(), test_db


def test_process_suppliers_route_rejects_blank_default_days(tmp_path, monkeypatch) -> None:
    app, test_db = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/process/suppliers/create",
        data={
            "supplier_id": "SUP-BLANK",
            "name": "空白默认周期供应商",
            "default_days": "",
            "status": "active",
        },
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "默认周期" in body

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Suppliers WHERE supplier_id=?", ("SUP-BLANK",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0
    finally:
        conn.close()
