"""插件启动的配置来源、失败状态与每次加载隔离。"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from data.repositories import SystemConfigRepository
from web.bootstrap import plugins

_LOGGER = logging.getLogger(__name__)


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
    with closing(get_connection(db_path)) as conn:
        SystemConfigRepository(conn).set("plugin.configured.enabled", "yes")
        conn.commit()
        status = plugins.bootstrap_plugins(str(tmp_path), conn, logger=_LOGGER)
        assert not conn.in_transaction

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

        empty = plugins.bootstrap_plugins(str(tmp_path / "empty"), conn, logger=_LOGGER)
        assert empty["statuses"] == []
        assert empty["registry"]["capabilities"] == []
        assert empty["degraded"] is False
        assert empty["degradation_events"] == []


def test_plugin_config_failure_retains_default_source(db_path, tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "default_enabled.py").write_text('PLUGIN_DEFAULT_ENABLED = "yes"\n', encoding="utf-8")

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("configuration unavailable")

    monkeypatch.setattr(SystemConfigRepository, "get_value", unavailable)

    with closing(get_connection(db_path)) as conn:
        status = plugins.bootstrap_plugins(str(tmp_path), conn, logger=_LOGGER)

    source = "default_due_to_config_read_failed"
    code = "plugin_bootstrap_config_read_failed"
    assert status["statuses"][0]["enabled_source"] == source
    assert status["statuses"][0]["loaded"] == "yes"
    assert status["config_source"] == source
    assert status["degraded"] is True
    assert len(status["degradation_events"]) == 1
    assert isinstance(status["degradation_events"][0], dict)
    assert status["degradation_events"][0]["code"] == code
    assert status["degradation_events"][0]["count"] == 1
    assert status["degradation_counters"] == {code: 1}


def test_plugin_bootstrap_rejects_connection_in_transaction(db_path, tmp_path):
    with closing(get_connection(db_path)) as conn:
        conn.execute("BEGIN")
        try:
            with pytest.raises(RuntimeError, match="outside any transaction"):
                plugins.bootstrap_plugins(str(tmp_path), conn, logger=_LOGGER)
        finally:
            conn.rollback()
