from __future__ import annotations

import os

import pytest
from flask import Flask

from web.bootstrap.security import ensure_secret_key


class _BadLogDir:
    def __str__(self) -> str:
        raise RuntimeError("log dir boom")


def test_ensure_secret_key_logs_invalid_log_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.config["LOG_DIR"] = _BadLogDir()
    warnings = []

    def _warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(app.logger, "warning", _warning)

    ensure_secret_key(app)

    assert str(app.config.get("SECRET_KEY") or "")
    assert any("LOG_DIR 配置解析失败" in message for message in warnings), warnings


def test_ensure_secret_key_invalid_log_dir_uses_stderr_when_logger_fails(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    app = Flask(__name__)
    app.config["LOG_DIR"] = _BadLogDir()

    def _boom_warning(message, *args, **kwargs):
        raise RuntimeError("logger boom")

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(app.logger, "warning", _boom_warning)

    ensure_secret_key(app)

    stderr_text = capsys.readouterr().err
    assert "LOG_DIR 配置解析失败" in stderr_text
