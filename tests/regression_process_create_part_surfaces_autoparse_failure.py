from __future__ import annotations

import importlib
import os
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

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), get_connection(str(test_db))


def test_process_create_part_surfaces_autoparse_failure(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    try:
        resp = client.post(
            "/process/parts/create",
            data={
                "part_no": "P_BAD",
                "part_name": "坏路线件",
                "route_raw": "bad",
                "remark": "",
            },
        )

        assert resp.status_code in (301, 302)
        assert resp.headers.get("Location", "").endswith("/process/parts/P_BAD")

        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any(cat == "success" and "已创建零件：P_BAD 坏路线件" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "零件已创建，但工序模板未成功生成" in msg for cat, msg in flashes), flashes

        part_row = conn.execute(
            "SELECT part_no, route_parsed FROM Parts WHERE part_no=?",
            ("P_BAD",),
        ).fetchone()
        assert part_row is not None
        assert str(part_row["route_parsed"] or "").strip().lower() == "no"

        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM PartOperations WHERE part_no=?", ("P_BAD",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 0
    finally:
        conn.close()
