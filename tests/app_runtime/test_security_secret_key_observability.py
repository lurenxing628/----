"""回归测试：ensure_secret_key 在 LOG_DIR 配置解析抛异常时仍能兜底生成 SECRET_KEY，并把「LOG_DIR 配置解析失败」告警写进 app.logger.warning；当 logger 本身也抛错时，该告警退回写到 stderr，不静默吞掉。"""

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


def _symlink_supported(tmp) -> bool:
    try:
        target = tmp / "_t"
        target.write_text("x", encoding="utf-8")
        link = tmp / "_l"
        os.symlink(target, link)
        link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


def test_ensure_secret_key_does_not_follow_symlink_on_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # finding-01 写侧：aps_secret_key.txt 是软链接时，重新生成密钥不得跟随软链接写穿、
    # 覆盖链接目标——写前移除软链接本身，新密钥写入 LOG_DIR 下真实普通文件。
    if not _symlink_supported(tmp_path):
        pytest.skip("平台不支持创建软链接（如 Win 无权限）")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")
    secret = log_dir / "aps_secret_key.txt"
    os.symlink(victim, secret)

    app = Flask(__name__)
    app.config["LOG_DIR"] = str(log_dir)
    ensure_secret_key(app)

    # 软链接未被跟随：目标文件内容原封不动
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"
    # secret 现在是真实普通文件（非软链接），写入了新密钥
    assert not os.path.islink(str(secret))
    assert os.path.isfile(str(secret))
    new_key = str(app.config.get("SECRET_KEY") or "")
    assert new_key and new_key in secret.read_text(encoding="utf-8")
