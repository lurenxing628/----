from __future__ import annotations

import sqlite3

from flask import Flask, g

from web.ui_mode import UI_MODE_COOKIE_KEY, get_ui_mode


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _create_system_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE SystemConfig (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          config_key TEXT UNIQUE,
          config_value TEXT,
          description TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def _set_ui_mode(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        """
        INSERT INTO SystemConfig (config_key, config_value, description)
        VALUES (?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
          config_value = excluded.config_value,
          description = excluded.description,
          updated_at = CURRENT_TIMESTAMP
        """,
        ("ui_mode", value, "UI mode for tests"),
    )
    conn.commit()


def _app() -> Flask:
    return Flask(__name__)


def test_get_ui_mode_prefers_cookie_over_db() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "v1")
        app = _app()
        with app.test_request_context("/", headers={"Cookie": f"{UI_MODE_COOKIE_KEY}=v2"}):
            g.db = conn
            assert get_ui_mode(default="v1") == "v2"
    finally:
        conn.close()


def test_get_ui_mode_reads_db_when_cookie_missing() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "v1")
        app = _app()
        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v2") == "v1"
    finally:
        conn.close()


def test_get_ui_mode_falls_back_to_default_for_invalid_db_value() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "invalid_mode")
        app = _app()
        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v1") == "v1"
    finally:
        conn.close()
