from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

import web.render_bridge as render_bridge_mod
import web.ui_mode as ui_mode_mod


class _ExplodingGlobals(dict):
    def setdefault(self, key, default=None):
        raise RuntimeError("globals boom")

    def __setitem__(self, key, value) -> None:
        raise RuntimeError("globals boom")


def _warning_collector(monkeypatch: pytest.MonkeyPatch, app: Flask):
    warnings = []

    def _warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _warning)
    return warnings


def test_init_ui_mode_static_dir_logger_failure_falls_back_to_stderr(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    app = Flask(__name__)

    def _boom_warning(message, *args, **kwargs):
        raise RuntimeError("logger boom")

    monkeypatch.setattr(app.logger, "warning", _boom_warning)
    monkeypatch.setattr(render_bridge_mod.os.path, "isdir", lambda path: False)

    ui_mode_mod.init_ui_mode(app, str(tmp_path))

    stderr_text = capsys.readouterr().err
    assert "V2 静态目录不存在" in stderr_text


def test_init_ui_mode_logs_v2_env_creation_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    (tmp_path / "web_new_test" / "static").mkdir(parents=True)
    warnings = _warning_collector(monkeypatch, app)

    monkeypatch.setattr(app.jinja_env, "overlay", lambda loader: (_ for _ in ()).throw(RuntimeError("overlay boom")))

    ui_mode_mod.init_ui_mode(app, str(tmp_path))

    assert app.extensions[ui_mode_mod._EXT_KEY_V2_ENV] is None
    assert any("初始化 V2 Jinja 环境失败" in message for message in warnings), warnings


def test_init_ui_mode_logs_main_globals_injection_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    (tmp_path / "web_new_test" / "static").mkdir(parents=True)
    warnings = _warning_collector(monkeypatch, app)

    app.jinja_env.globals = _ExplodingGlobals()
    monkeypatch.setattr(app.jinja_env, "overlay", lambda loader: SimpleNamespace(globals={}))

    ui_mode_mod.init_ui_mode(app, str(tmp_path))

    assert any("初始化主模板环境全局函数注入失败" in message for message in warnings), warnings
    assert any("模板宏" in message for message in warnings), warnings


def test_init_ui_mode_logs_v2_globals_injection_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    (tmp_path / "web_new_test" / "static").mkdir(parents=True)
    warnings = _warning_collector(monkeypatch, app)

    monkeypatch.setattr(app.jinja_env, "overlay", lambda loader: SimpleNamespace(globals=_ExplodingGlobals()))

    ui_mode_mod.init_ui_mode(app, str(tmp_path))

    assert any("初始化 V2 模板环境全局函数注入失败" in message for message in warnings), warnings
