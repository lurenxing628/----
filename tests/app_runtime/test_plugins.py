"""插件启动的配置来源、失败状态与每次加载隔离。"""

from __future__ import annotations

import sqlite3

import pytest

from core.infrastructure.database import get_connection
from data.repositories import SystemConfigRepository
from web.bootstrap import plugins


def test_plugin_bootstrap_preserves_sources_and_public_failures(db_path, tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "configured.py").write_text(
        'PLUGIN_DEFAULT_ENABLED = "no"\n'
        'def register(registry):\n'
        '    registry.register("solver.configured", "provider")\n',
        encoding="utf-8",
    )
    (plugin_dir / "disabled.py").write_text('PLUGIN_DEFAULT_ENABLED = "no"\n', encoding="utf-8")
    (plugin_dir / "failed.py").write_text(
        'PLUGIN_DEFAULT_ENABLED = "yes"\n'
        'def register(registry):\n'
        '    registry.register("solver.failed", "partial-provider")\n'
        '    raise RuntimeError("private plugin details")\n',
        encoding="utf-8",
    )
    conn = get_connection(db_path)
    SystemConfigRepository(conn).set("plugin.configured.enabled", "yes")
    conn.commit()
    conn.close()

    status = plugins.bootstrap_plugins(str(tmp_path), db_path)

    rows = {row["plugin_id"]: row for row in status["statuses"]}
    assert rows["configured"]["enabled_source"] == "config"
    assert rows["configured"]["loaded"] == "yes"
    assert rows["disabled"]["enabled_source"] == "default"
    assert rows["failed"]["loaded"] == "no"
    assert rows["failed"]["error"] == "插件加载失败，请联系维护人员检查系统运行记录。"
    assert status["registry"]["capabilities"] == ["solver.configured"]
    assert status["config_source"] == "mixed"
    assert status["degraded"] is True
    assert status["degradation_events"] == [
        {
            "code": "plugin_bootstrap_load_failed",
            "message": "插件加载失败，请联系维护人员检查系统运行记录。",
            "count": 1,
        }
    ]
    assert status["degradation_counters"] == {"plugin_bootstrap_load_failed": 1}
    assert status["telemetry_persisted"] is True

    empty = plugins.bootstrap_plugins(str(tmp_path / "empty"), db_path)
    assert empty["statuses"] == []
    assert empty["registry"]["capabilities"] == []
    assert empty["degraded"] is False
    assert empty["degradation_events"] == []


@pytest.mark.parametrize(
    ("failure", "source", "code"),
    [
        ("database", "default_due_to_db_unavailable", "plugin_bootstrap_db_unavailable"),
        ("value", "default_due_to_config_read_failed", "plugin_bootstrap_config_read_failed"),
    ],
)
def test_plugin_config_failure_retains_default_source(db_path, tmp_path, monkeypatch, failure, source, code):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "default_enabled.py").write_text('PLUGIN_DEFAULT_ENABLED = "yes"\n', encoding="utf-8")

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("configuration unavailable")

    if failure == "database":
        monkeypatch.setattr(plugins, "get_connection", unavailable)
    else:
        monkeypatch.setattr(SystemConfigRepository, "get_value", unavailable)

    status = plugins.bootstrap_plugins(str(tmp_path), db_path)

    assert status["statuses"][0]["enabled_source"] == source
    assert status["statuses"][0]["loaded"] == "yes"
    assert status["config_source"] == source
    assert status["degraded"] is True
    assert len(status["degradation_events"]) == 1
    assert isinstance(status["degradation_events"][0], dict)
    assert status["degradation_events"][0]["code"] == code
    assert status["degradation_events"][0]["count"] == 1
    assert status["degradation_counters"] == {code: 1}
