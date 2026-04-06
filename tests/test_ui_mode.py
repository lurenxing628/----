from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from flask import Flask, g
from jinja2 import DictLoader

from web import ui_mode as ui_mode_mod
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


def _template_app() -> Flask:
    app = Flask(__name__)
    app.jinja_env.loader = DictLoader(
        {
            "demo.html": "{{ ui_mode }}|{{ ui_template_env }}|{{ 1 if ui_template_env_degraded else 0 }}",
        }
    )
    return app


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


def test_get_ui_mode_falls_back_to_default_for_invalid_db_value(monkeypatch) -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "invalid_mode")
        app = _app()
        warnings = []

        def _fake_warning(message, *args, **kwargs):
            warnings.append(message % args if args else str(message))

        monkeypatch.setattr(app.logger, "warning", _fake_warning)
        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v1") == "v1"
        assert any("UI 模式数据库配置非法" in msg and "invalid_mode" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_get_ui_mode_logs_invalid_db_value_once_per_request(monkeypatch) -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "invalid_mode")
        app = _app()
        warnings = []

        def _fake_warning(message, *args, **kwargs):
            warnings.append(message % args if args else str(message))

        monkeypatch.setattr(app.logger, "warning", _fake_warning)

        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v1") == "v1"
            assert get_ui_mode(default="v1") == "v1"

        invalid_warnings = [msg for msg in warnings if "UI 模式数据库配置非法" in msg]
        assert len(invalid_warnings) == 1, warnings
    finally:
        conn.close()


def test_get_ui_mode_logs_warning_when_cookie_read_fails(monkeypatch) -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "v1")
        app = _app()
        warnings = []

        def _fake_warning(message, *args, **kwargs):
            warnings.append(message % args if args else str(message))

        class _RaisingCookies:
            def get(self, *args, **kwargs):
                raise RuntimeError("cookie exploded")

        monkeypatch.setattr(app.logger, "warning", _fake_warning)
        monkeypatch.setattr(ui_mode_mod, "request", SimpleNamespace(cookies=_RaisingCookies()))

        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v2") == "v1"

        assert any("读取 UI 模式 cookie 失败" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_get_ui_mode_logs_warning_when_db_read_fails(monkeypatch) -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        app = _app()
        warnings = []

        def _fake_warning(message, *args, **kwargs):
            warnings.append(message % args if args else str(message))

        class _ExplodingSystemConfigService:
            def __init__(self, conn, logger=None):
                self.conn = conn
                self.logger = logger

            def get_value(self, key, default=None):
                raise RuntimeError(f"db exploded: {key}")

        monkeypatch.setattr(app.logger, "warning", _fake_warning)
        monkeypatch.setattr(ui_mode_mod, "SystemConfigService", _ExplodingSystemConfigService)

        with app.test_request_context("/"):
            g.db = conn
            assert get_ui_mode(default="v2") == "v2"

        assert any("读取 UI 模式数据库配置失败" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_safe_url_for_logs_warning_on_non_build_error(monkeypatch) -> None:
    app = _app()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    monkeypatch.setattr(ui_mode_mod, "url_for", lambda endpoint, **values: (_ for _ in ()).throw(RuntimeError("boom")))

    with app.test_request_context("/demo"):
        assert ui_mode_mod.safe_url_for("missing.endpoint") is None

    assert any("模板链接构建失败" in msg for msg in warnings), warnings


def test_render_ui_template_warns_once_when_v2_env_missing(monkeypatch) -> None:
    app = _template_app()
    app.extensions[ui_mode_mod._EXT_KEY_V2_ENV] = None
    app.extensions[ui_mode_mod._EXT_KEY_V2_RENDER_FALLBACK_WARNED] = False

    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.test_request_context("/demo"):
        first = ui_mode_mod.render_ui_template("demo.html")
        second = ui_mode_mod.render_ui_template("demo.html")

    assert first == "v2|v1_fallback|1"
    assert second == "v2|v1_fallback|1"
    assert len(warnings) == 1
    assert "mode=v2 but v2_env missing" in warnings[0]
    assert "template=demo.html" in warnings[0]
    assert "path=/demo" in warnings[0]


def test_render_ui_template_sets_degraded_context_when_v2_env_missing() -> None:
    app = _template_app()
    app.extensions[ui_mode_mod._EXT_KEY_V2_ENV] = None
    app.extensions[ui_mode_mod._EXT_KEY_V2_RENDER_FALLBACK_WARNED] = False

    with app.test_request_context("/demo"):
        rendered = ui_mode_mod.render_ui_template("demo.html")
        assert g.ui_mode == "v2"
        assert g.ui_template_env == "v1_fallback"
        assert g.ui_template_env_degraded is True

    assert rendered == "v2|v1_fallback|1"
