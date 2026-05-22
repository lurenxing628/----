from __future__ import annotations

import pytest
from flask import Flask


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []

    def warning(self, message: str) -> None:
        self.warnings.append(str(message))


def test_versioned_url_for_logs_missing_static_file_once(tmp_path) -> None:
    from web.bootstrap.static_versioning import build_versioned_url_for

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        assert versioned_url_for("static", filename="missing.css") == "/static/missing.css"
        assert versioned_url_for("static", filename="missing.css") == "/static/missing.css"

    assert len(app.logger.warnings) == 1
    assert "静态资源版本号读取失败" in app.logger.warnings[0]


def test_install_versioned_url_for_logs_jinja_injection_failure(tmp_path) -> None:
    from web.bootstrap.static_versioning import EXT_KEY_TEMPLATE_URL_FOR, install_versioned_url_for

    class _BrokenGlobals(dict):
        def __setitem__(self, key, value):
            raise RuntimeError("globals locked")

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    app.jinja_env.globals = _BrokenGlobals()

    install_versioned_url_for(app, str(tmp_path))

    assert EXT_KEY_TEMPLATE_URL_FOR in app.extensions
    assert any("模板静态资源版本函数注入失败" in item for item in app.logger.warnings)


def test_versioned_url_for_does_not_hide_unexpected_filename_errors(tmp_path) -> None:
    from web.bootstrap.static_versioning import build_versioned_url_for

    class _BrokenFilename:
        def __str__(self) -> str:
            raise RuntimeError("filename exploded")

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        with pytest.raises(RuntimeError, match="filename exploded"):
            versioned_url_for("static", filename=_BrokenFilename())
