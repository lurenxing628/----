from __future__ import annotations

import web.bootstrap.factory as factory_mod


class _ImmediateThread:
    def __init__(self, *, target, daemon: bool) -> None:
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        self._target()


class _BoomServer:
    def shutdown(self) -> None:
        raise RuntimeError("shutdown boom")


class _Logger:
    def __init__(self) -> None:
        self.messages = []

    def warning(self, message, *args) -> None:
        self.messages.append(message % args if args else str(message))


def test_request_runtime_server_shutdown_logs_warning_when_logger_available(monkeypatch) -> None:
    logger = _Logger()

    monkeypatch.setattr(factory_mod, "_RUNTIME_SERVER", _BoomServer())
    monkeypatch.setattr(factory_mod, "_RUNTIME_SERVER_SHUTDOWN_REQUESTED", False)
    monkeypatch.setattr(
        factory_mod.threading,
        "Thread",
        lambda target, daemon=True: _ImmediateThread(target=target, daemon=daemon),
    )

    assert factory_mod.request_runtime_server_shutdown(logger=logger) is True
    assert any("请求运行时 Server 关闭失败" in message for message in logger.messages), logger.messages


def test_request_runtime_server_shutdown_writes_stderr_when_logger_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(factory_mod, "_RUNTIME_SERVER", _BoomServer())
    monkeypatch.setattr(factory_mod, "_RUNTIME_SERVER_SHUTDOWN_REQUESTED", False)
    monkeypatch.setattr(
        factory_mod.threading,
        "Thread",
        lambda target, daemon=True: _ImmediateThread(target=target, daemon=daemon),
    )

    assert factory_mod.request_runtime_server_shutdown(logger=None) is True
    stderr_text = capsys.readouterr().err
    assert "请求运行时 Server 关闭失败" in stderr_text
