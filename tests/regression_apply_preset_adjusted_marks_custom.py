from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_apply_preset_missing_required_fields_is_rejected_without_writing_snapshot() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        base = cfg_svc.get_snapshot().to_dict()
        payload = dict(base)
        payload.pop("priority_weight", None)
        payload.pop("due_weight", None)

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("缺省字段方案"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="regression preset",
            )

        before = cfg_svc.get_snapshot(strict_mode=True).to_dict()

        applied = cfg_svc.apply_preset("缺省字段方案")
        assert applied["status"] == "rejected"
        assert applied["requested_preset"] == "缺省字段方案"
        assert applied["effective_active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert applied["adjusted_fields"] == []
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None
        assert applied["error_fields"] == ["priority_weight", "due_weight"]
        error_message = str(applied["error_message"] or "")
        assert "priority_weight" in error_message
        assert "due_weight" in error_message

        snap = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        assert snap == before
    finally:
        conn.close()
