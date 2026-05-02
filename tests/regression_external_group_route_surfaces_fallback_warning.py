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
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
        ("P001", "零件", "", "yes"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 10, "表处理", "external", None, 2.0, "G001", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("G001", "P001", 10, 10, "separate", None, None, None),
    )
    conn.commit()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), conn


def test_external_group_route_surfaces_fallback_warning(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    try:
        resp = client.post(
            "/process/parts/P001/groups/G001/mode",
            data={
                "merge_mode": "separate",
                "ext_days_10": "",
            },
        )

        assert resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any(cat == "success" and "外协工序组周期模式已更新" in msg for cat, msg in flashes), flashes
        assert any(cat == "warning" and "本次会先按 1 天记录" in msg for cat, msg in flashes), flashes
        assert not any("compatible mode" in msg or "raw=" in msg or "ext_days" in msg for _cat, msg in flashes), flashes

        row = conn.execute(
            "SELECT ext_days FROM PartOperations WHERE part_no=? AND seq=?",
            ("P001", 10),
        ).fetchone()
        assert row is not None and abs(float(row["ext_days"] or 0.0) - 1.0) < 1e-9
    finally:
        conn.close()
