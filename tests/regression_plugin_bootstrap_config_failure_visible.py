from __future__ import annotations

from pathlib import Path
from unittest import mock

from core.infrastructure.database import ensure_schema
from web.bootstrap.plugins import bootstrap_plugins

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_demo_plugin(base_dir: Path) -> None:
    plugins_dir = base_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "demo_plugin.py").write_text(
        "PLUGIN_ID = 'demo_plugin'\n"
        "PLUGIN_NAME = '演示插件'\n"
        "PLUGIN_DEFAULT_ENABLED = 'yes'\n"
        "def register(registry):\n"
        "    registry.register('demo.capability', object())\n",
        encoding="utf-8",
    )


def _write_failing_plugin(base_dir: Path) -> None:
    plugins_dir = base_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "failing_plugin.py").write_text(
        "PLUGIN_ID = 'failing_plugin'\n"
        "PLUGIN_NAME = '失败插件'\n"
        "PLUGIN_DEFAULT_ENABLED = 'yes'\n"
        "def register(registry):\n"
        "    raise RuntimeError('PLUGIN_INTERNAL_SECRET')\n",
        encoding="utf-8",
    )


def test_plugin_bootstrap_db_failure_visible(tmp_path: Path) -> None:
    db_path = tmp_path / "aps.db"
    _write_demo_plugin(tmp_path)

    with mock.patch("web.bootstrap.plugins.get_connection", side_effect=RuntimeError("db down")):
        plugin_status = bootstrap_plugins(base_dir=str(tmp_path), database_path=str(db_path), logger=None)

    assert isinstance(plugin_status, dict), plugin_status
    assert plugin_status.get("degraded") is True, plugin_status
    assert plugin_status.get("config_source") == "default_due_to_db_unavailable", plugin_status

    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_db_unavailable") or 0) == 1, counters

    statuses = list(plugin_status.get("statuses") or [])
    row = next(item for item in statuses if str(item.get("plugin_id") or "") == "demo_plugin")
    assert row.get("enabled_source") == "default_due_to_db_unavailable", row
    assert row.get("enabled") == "yes", row
    assert row.get("loaded") == "yes", row


def test_plugin_bootstrap_config_read_failure_visible(tmp_path: Path) -> None:
    db_path = tmp_path / "aps.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ensure_schema(str(db_path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(backup_dir))
    _write_demo_plugin(tmp_path)

    with mock.patch("web.bootstrap.plugins.SystemConfigRepository.get_value", side_effect=RuntimeError("read boom")):
        plugin_status = bootstrap_plugins(base_dir=str(tmp_path), database_path=str(db_path), logger=None)

    assert isinstance(plugin_status, dict), plugin_status
    assert plugin_status.get("degraded") is True, plugin_status
    assert plugin_status.get("config_source") == "default_due_to_config_read_failed", plugin_status

    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_config_read_failed") or 0) == 1, counters

    events = list(plugin_status.get("degradation_events") or [])
    assert any(str(evt.get("code") or "") == "plugin_bootstrap_config_read_failed" for evt in events), events
    assert all("sample" not in evt for evt in events), events
    assert "RuntimeError" not in str(events), events

    statuses = list(plugin_status.get("statuses") or [])
    row = next(item for item in statuses if str(item.get("plugin_id") or "") == "demo_plugin")
    assert row.get("enabled_source") == "default_due_to_config_read_failed", row
    assert row.get("enabled") == "yes", row
    assert row.get("loaded") == "yes", row


def test_plugin_bootstrap_status_error_is_public_message(tmp_path: Path) -> None:
    db_path = tmp_path / "aps.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ensure_schema(str(db_path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(backup_dir))
    _write_failing_plugin(tmp_path)

    plugin_status = bootstrap_plugins(base_dir=str(tmp_path), database_path=str(db_path), logger=None)

    statuses = list(plugin_status.get("statuses") or [])
    row = next(item for item in statuses if str(item.get("plugin_id") or "") == "failing_plugin")
    assert row.get("loaded") == "no", row
    assert row.get("error") == "插件加载失败，请查看系统日志。", row
    assert "PLUGIN_INTERNAL_SECRET" not in str(plugin_status), plugin_status


def test_plugin_bootstrap_status_snapshot_failure_visible(tmp_path: Path) -> None:
    db_path = tmp_path / "aps.db"
    _write_demo_plugin(tmp_path)

    with mock.patch(
        "web.bootstrap.plugins.PluginManager.load_from_base_dir",
        side_effect=RuntimeError("load boom"),
    ), mock.patch(
        "web.bootstrap.plugins.get_plugin_status",
        side_effect=RuntimeError("status boom"),
    ):
        plugin_status = bootstrap_plugins(base_dir=str(tmp_path), database_path=str(db_path), logger=None)

    assert isinstance(plugin_status, dict), plugin_status
    assert plugin_status.get("degraded") is True, plugin_status

    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_status_snapshot_failed") or 0) == 1, counters
    assert list(plugin_status.get("statuses") or []) == [], plugin_status
    events = list(plugin_status.get("degradation_events") or [])
    assert any(str(evt.get("code") or "") == "plugin_bootstrap_status_snapshot_failed" for evt in events), events
    assert all("sample" not in evt for evt in events), events
    assert "status boom" not in str(events), events
