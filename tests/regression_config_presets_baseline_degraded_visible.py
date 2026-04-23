from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.services.scheduler.config import config_presets
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    _load_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def test_dirty_partial_store_does_not_fabricate_active_preset_provenance(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO ScheduleConfig (config_key, config_value, description)
        VALUES (?, ?, ?)
        """,
        ("holiday_default_efficiency", "0", "broken baseline"),
    )
    conn.commit()

    cfg_svc = ConfigService(conn, logger=None, op_logger=None)
    cfg_svc.ensure_defaults()
    display_state = cfg_svc.get_preset_display_state(readonly=True)

    assert cfg_svc.get_active_preset() is None
    assert cfg_svc.get_active_preset_reason() is None
    assert display_state["active_preset_missing"] is True
    assert display_state["current_config_state"]["provenance_missing"] is True


def test_baseline_probe_exception_is_visible_in_reason(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_svc = ConfigService(conn, logger=None, op_logger=None)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(config_presets, "get_snapshot_from_repo", _boom)
    cfg_svc.ensure_defaults()

    assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
    reason = cfg_svc.get_active_preset_reason() or ""
    assert cfg_svc.ACTIVE_PRESET_REASON_BASELINE_DEGRADED in reason
    assert "RuntimeError" in reason
