from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_apply_preset_adjusted_marks_custom() -> None:
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

        applied = cfg_svc.apply_preset("缺省字段方案")
        assert applied == "缺省字段方案"
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        reason = cfg_svc.get_active_preset_reason() or ""
        assert ("规范化" in reason) or ("修补" in reason), f"preset 调整后 reason 异常：{reason!r}"

        snap = cfg_svc.get_snapshot()
        assert abs(float(snap.priority_weight) - float(base["priority_weight"])) < 1e-9
        assert abs(float(snap.due_weight) - float(base["due_weight"])) < 1e-9
    finally:
        conn.close()
