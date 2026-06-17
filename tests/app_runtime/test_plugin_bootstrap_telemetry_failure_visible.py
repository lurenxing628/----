"""回归测试：bootstrap_plugins 在插件遥测落库失败（OperationLogger.info 返回 False）时必须显式降级——telemetry_persisted=False、degraded=True、计数器 plugin_bootstrap_telemetry_failed=1 并产出不带样本数据的降级事件，插件本身仍正常注册，不得静默吞掉。"""

from __future__ import annotations

import os
from unittest import mock


def test_plugin_bootstrap_telemetry_failure_visible(db_path, tmp_path) -> None:
    from web.bootstrap.plugins import bootstrap_plugins

    tmpdir = str(tmp_path)
    backup_dir = os.path.join(tmpdir, "backups")
    plugins_dir = os.path.join(tmpdir, "plugins")
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(plugins_dir, exist_ok=True)

    plugin_path = os.path.join(plugins_dir, "demo_plugin.py")
    with open(plugin_path, "w", encoding="utf-8") as fh:
        fh.write(
            "PLUGIN_ID = 'demo_plugin'\n"
            "PLUGIN_NAME = '演示插件'\n"
            "PLUGIN_DEFAULT_ENABLED = 'yes'\n"
            "def register(registry):\n"
            "    registry.register('demo.capability', object())\n"
        )

    with mock.patch("web.bootstrap.plugins.OperationLogger") as mocked_logger_cls:
        mocked_logger_cls.return_value.info.return_value = False
        plugin_status = bootstrap_plugins(base_dir=tmpdir, database_path=db_path, logger=None)

    assert isinstance(plugin_status, dict), plugin_status
    assert plugin_status.get("telemetry_persisted") is False, plugin_status
    assert plugin_status.get("degraded") is True, plugin_status

    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_telemetry_failed") or 0) == 1, counters

    events = list(plugin_status.get("degradation_events") or [])
    assert any(str(evt.get("code") or "") == "plugin_bootstrap_telemetry_failed" for evt in events), events
    assert all("sample" not in evt for evt in events), events

    statuses = list(plugin_status.get("statuses") or [])
    assert any(str(item.get("plugin_id") or "") == "demo_plugin" for item in statuses), statuses
