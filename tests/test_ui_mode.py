from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest
from flask import Flask, g
from jinja2 import DictLoader

from core.services.system import SystemConfigService
from web import ui_mode as ui_mode_mod
from web.ui_mode import UI_MODE_COOKIE_KEY, get_ui_mode, normalize_manual_src


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


def _set_ui_mode(conn: sqlite3.Connection, value) -> None:
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


def _attach_system_config_service(app: Flask, conn: sqlite3.Connection, *, service=None) -> None:
    g.db = conn
    g.services = SimpleNamespace(
        system_config_service=service or SystemConfigService(conn, logger=app.logger),
    )


def test_get_ui_mode_prefers_cookie_over_db() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "v1")
        app = _app()
        with app.test_request_context("/", headers={"Cookie": f"{UI_MODE_COOKIE_KEY}=v2"}):
            _attach_system_config_service(app, conn)
            assert get_ui_mode(default="v1") == "v2"
    finally:
        conn.close()


def test_normalize_manual_src_accepts_same_origin_absolute_url_and_preserves_trailing_question_mark() -> None:
    app = _app()

    with app.test_request_context("/scheduler/config/manual", base_url="http://localhost/"):
        assert normalize_manual_src("http://localhost/scheduler/config?") == "/scheduler/config?"


def test_get_ui_mode_reads_db_when_cookie_missing() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, "v1")
        app = _app()
        with app.test_request_context("/"):
            _attach_system_config_service(app, conn)
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
            _attach_system_config_service(app, conn)
            assert get_ui_mode(default="v1") == "v1"
        assert any("UI 模式数据库配置非法" in msg and "invalid_mode" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_get_ui_mode_treats_null_db_value_as_invalid_and_logs_warning(monkeypatch) -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        _set_ui_mode(conn, None)
        app = _app()
        warnings = []

        def _fake_warning(message, *args, **kwargs):
            warnings.append(message % args if args else str(message))

        monkeypatch.setattr(app.logger, "warning", _fake_warning)
        with app.test_request_context("/"):
            _attach_system_config_service(app, conn)
            assert get_ui_mode(default="v1") == "v1"
        assert any("UI 模式数据库配置非法" in msg for msg in warnings), warnings
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
            _attach_system_config_service(app, conn)
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
            _attach_system_config_service(app, conn)
            assert get_ui_mode(default="v2") == "v1"

        assert any("读取 UI 模式 cookie 失败" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_read_ui_mode_missing_without_request_context() -> None:
    result = ui_mode_mod._read_ui_mode_from_db()
    assert result.missing is True
    assert result.mode is None


def test_read_ui_mode_missing_when_main_path_has_no_db_and_does_not_touch_services() -> None:
    app = _app()

    class _ExplodingServices:
        @property
        def system_config_service(self):
            raise AssertionError("无 g.db 的短路路径不应访问容器")

    with app.test_request_context("/"):
        g.services = _ExplodingServices()
        result = ui_mode_mod._read_ui_mode_from_db()

    assert result.missing is True
    assert result.mode is None


def test_read_ui_mode_raises_when_db_exists_but_services_missing() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        app = _app()
        with app.test_request_context("/"):
            g.db = conn
            with pytest.raises(RuntimeError, match=r"g\.services"):
                ui_mode_mod._read_ui_mode_from_db()
    finally:
        conn.close()


def test_read_ui_mode_raises_when_system_config_service_missing() -> None:
    app = _app()
    with app.test_request_context("/"):
        g.db = object()
        g.services = SimpleNamespace()
        with pytest.raises(RuntimeError, match=r"system_config_service"):
            ui_mode_mod._read_ui_mode_from_db()


def test_get_ui_mode_raises_when_system_config_service_access_fails() -> None:
    conn = _mem_conn()
    try:
        _create_system_config(conn)
        app = _app()

        class _ExplodingServices:
            @property
            def system_config_service(self):
                raise RuntimeError("construct exploded")

        with app.test_request_context("/"):
            g.db = conn
            g.services = _ExplodingServices()
            with pytest.raises(RuntimeError, match=r"system_config_service 构造失败"):
                get_ui_mode(default="v2")

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

        class _ReadExplodedSystemConfigService:
            def get_value_with_presence(self, key):
                raise RuntimeError(f"db exploded: {key}")

        monkeypatch.setattr(app.logger, "warning", _fake_warning)

        with app.test_request_context("/"):
            _attach_system_config_service(app, conn, service=_ReadExplodedSystemConfigService())
            assert get_ui_mode(default="v2") == "v2"

        assert any("读取 UI 模式数据库配置失败" in msg for msg in warnings), warnings
    finally:
        conn.close()


def test_read_ui_mode_raises_when_system_config_service_missing_single_query_interface() -> None:
    app = _app()
    with app.test_request_context("/"):
        g.db = object()
        g.services = SimpleNamespace(system_config_service=SimpleNamespace())
        with pytest.raises(RuntimeError, match=r"get_value_with_presence"):
            ui_mode_mod._read_ui_mode_from_db()


def test_read_ui_mode_accepts_single_query_service_without_legacy_interfaces() -> None:
    app = _app()

    class _SingleQueryService:
        def get_value_with_presence(self, key):
            assert key == ui_mode_mod.UI_MODE_CONFIG_KEY
            return True, "v1"

    with app.test_request_context("/"):
        g.db = object()
        g.services = SimpleNamespace(system_config_service=_SingleQueryService())
        result = ui_mode_mod._read_ui_mode_from_db()

    assert result.mode == "v1"
    assert result.missing is False


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
        assert g.ui_template_source == "base_fallback"

    assert rendered == "v2|v1_fallback|1"


def test_render_ui_template_marks_base_loader_resolution_as_degraded(tmp_path, monkeypatch) -> None:
    base_templates = tmp_path / "templates"
    base_templates.mkdir(parents=True)
    (base_templates / "demo.html").write_text(
        "{{ ui_mode }}|{{ ui_template_env }}|{{ ui_template_source }}|{{ 1 if ui_template_env_degraded else 0 }}",
        encoding="utf-8",
    )
    (tmp_path / "web_new_test" / "templates").mkdir(parents=True)
    (tmp_path / "web_new_test" / "static").mkdir(parents=True)

    app = Flask(__name__, template_folder=str(base_templates))
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    ui_mode_mod.init_ui_mode(app, str(tmp_path))
    monkeypatch.setattr(ui_mode_mod, "get_ui_mode", lambda default=None: "v2")

    with app.test_request_context("/demo"):
        rendered = ui_mode_mod.render_ui_template("demo.html")
        assert g.ui_template_env == "v2"
        assert g.ui_template_source == "base_fallback"
        assert g.ui_template_env_degraded is True

    assert rendered == "v2|v2|base_fallback|1"
    assert len(warnings) == 1, warnings
    assert "mode=v2 but template resolved via base loader" in warnings[0]
    assert "template=demo.html" in warnings[0]
    assert "path=/demo" in warnings[0]


def test_render_ui_template_logs_warning_when_env_globals_bridge_injection_fails(monkeypatch) -> None:
    app = _app()
    warnings = []

    class _ExplodingGlobals(dict):
        def setdefault(self, key, default=None):
            raise RuntimeError("globals bridge exploded")

        def __setitem__(self, key, value) -> None:
            raise RuntimeError("globals bridge exploded")

    class _TemplateStub:
        def render(self, context):
            return "rendered"

    class _EnvStub:
        def __init__(self) -> None:
            self.globals = _ExplodingGlobals()

        def get_or_select_template(self, template_name_or_list):
            assert template_name_or_list == "demo.html"
            return _TemplateStub()

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    monkeypatch.setattr(ui_mode_mod, "get_ui_mode", lambda default=None: "v2")
    monkeypatch.setattr(ui_mode_mod, "_get_v2_env", lambda current_app: _EnvStub())

    with app.test_request_context("/bridge"):
        rendered = ui_mode_mod.render_ui_template("demo.html")

    assert rendered == "rendered"
    assert len(warnings) == 1, warnings
    assert "模板环境全局函数注入失败" in warnings[0]
    assert "template=demo.html" in warnings[0]
    assert "path=/bridge" in warnings[0]
