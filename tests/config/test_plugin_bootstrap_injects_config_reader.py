"""回归测试：bootstrap_plugins 向 PluginManager.load_from_base_dir 注入的是只读 config_reader 回调（基于 SystemConfigRepository 解析 plugin.<name>.enabled），而非裸 conn；回调能正确读出 plugin.demo_plugin.enabled=yes，且返回的状态字典原样透传 plugins_dir/conflict_policy/statuses/registry。"""

from __future__ import annotations

import os
from unittest import mock


class _DummyConn:
    def close(self) -> None:
        return None


class _DummyConfigRepo:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.calls = []

    def get_value(self, key: str, default=None):
        self.calls.append((str(key), default))
        if str(key) == "plugin.demo_plugin.enabled":
            return "yes"
        return default


def test_plugin_bootstrap_injects_config_reader() -> None:
    from web.bootstrap.plugins import bootstrap_plugins

    captured = {}

    def _stub_load_from_base_dir(base_dir: str, **kwargs):
        captured["base_dir"] = base_dir
        captured["kwargs"] = dict(kwargs or {})
        reader = kwargs.get("config_reader")
        captured["reader_value"] = reader("demo_plugin") if callable(reader) else None
        return {
            "loaded_at": "2026-04-04 20:00:00",
            "vendor_paths": [],
            "plugins_dir": os.path.join(base_dir, "plugins"),
            "statuses": [],
            "registry": {"capabilities": []},
            "conflicted_capabilities": [],
            "conflict_policy": "first_loaded_wins",
        }

    with mock.patch("web.bootstrap.plugins.get_connection", return_value=_DummyConn()), mock.patch(
        "web.bootstrap.plugins.SystemConfigRepository", _DummyConfigRepo
    ), mock.patch("web.bootstrap.plugins.PluginManager.load_from_base_dir", side_effect=_stub_load_from_base_dir), mock.patch(
        "web.bootstrap.plugins.OperationLogger"
    ) as mocked_logger_cls:
        mocked_logger_cls.return_value.info.return_value = True
        status = bootstrap_plugins(base_dir="D:/demo", database_path="D:/demo/aps.db", logger=None)

    kwargs = captured.get("kwargs") or {}
    assert callable(kwargs.get("config_reader")), captured
    assert captured.get("reader_value") == "yes", captured
    assert "conn" not in kwargs, captured
    assert isinstance(status, dict), status
    assert status.get("plugins_dir") == os.path.join("D:/demo", "plugins"), status
    assert status.get("conflict_policy") == "first_loaded_wins", status
    assert "statuses" in status and "registry" in status and "plugins_dir" in status, status
