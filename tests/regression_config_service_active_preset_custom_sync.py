from __future__ import annotations

import sqlite3
from pathlib import Path

from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_config_service_manual_set_marks_active_preset_custom() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None

        saved = cfg_svc.save_preset("我的方案")
        assert saved == "我的方案"
        assert cfg_svc.get_active_preset() == "我的方案"
        assert cfg_svc.get_active_preset_reason() is None

        cfg_svc.set_dispatch("sgs", "slack")
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        reason = cfg_svc.get_active_preset_reason() or ""
        assert "手工" in reason, f"手工修改后 active_preset_reason 异常：{reason!r}"
    finally:
        conn.close()
