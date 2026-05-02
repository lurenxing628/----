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
    conn = get_connection(str(test_db))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EXT", "表处理", "external"))
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
        ("P001", "零件", "", "no", None),
    )
    conn.commit()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), conn


def test_process_reparse_part_surfaces_warning_text(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    try:
        resp = client.post(
            "/process/parts/P001/reparse",
            data={
                "route_raw": "10表处理",
            },
        )

        assert resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any(cat == "success" and "工艺路线解析完成：共 1 道工序" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "工种“表处理”没有找到可用的外协供应商，本次会先按 1 天安排。建议补好供应商和周期。" in msg
            for cat, msg in flashes
        ), flashes

        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM PartOperations WHERE part_no=?",
            ("P001",),
        ).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 1
    finally:
        conn.close()
