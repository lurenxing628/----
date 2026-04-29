from __future__ import annotations

from pathlib import Path
from unittest import mock

from core.infrastructure.database import ensure_schema
from core.plugins import PluginManager, get_plugin_registry
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.openpyxl_backend import OpenpyxlBackend
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


def _write_excel_backend_plugin(base_dir: Path) -> None:
    plugins_dir = base_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "excel_backend_plugin.py").write_text(
        "from core.services.common.tabular_backend import TabularBackend\n"
        "PLUGIN_ID = 'pandas_excel_backend'\n"
        "PLUGIN_NAME = '演示 Excel 后端插件'\n"
        "PLUGIN_DEFAULT_ENABLED = 'yes'\n"
        "class DemoPandasBackend(TabularBackend):\n"
        "    def read(self, file_path, sheet=None):\n"
        "        return []\n"
        "    def write(self, rows, file_path, sheet='Sheet1'):\n"
        "        return None\n"
        "def register(registry):\n"
        "    registry.register('excel_backend.pandas', lambda: DemoPandasBackend())\n",
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
    assert plugin_status.get("degraded") is True, plugin_status
    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_load_failed") or 0) == 1, counters


def test_plugin_bootstrap_load_failure_does_not_reuse_old_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "aps.db"
    old_base = tmp_path / "old"
    new_base = tmp_path / "new"
    _write_excel_backend_plugin(old_base)
    _write_demo_plugin(new_base)
    old_status = PluginManager.load_from_base_dir(str(old_base), logger=None)
    assert dict(old_status.get("registry") or {}).get("capabilities") == ["excel_backend.pandas"], old_status
    assert get_excel_backend().__class__.__name__ == "DemoPandasBackend"

    with mock.patch(
        "web.bootstrap.plugins.PluginManager.load_from_base_dir",
        side_effect=RuntimeError("load boom"),
    ):
        plugin_status = bootstrap_plugins(base_dir=str(new_base), database_path=str(db_path), logger=None)

    assert isinstance(plugin_status, dict), plugin_status
    assert plugin_status.get("degraded") is True, plugin_status

    counters = dict(plugin_status.get("degradation_counters") or {})
    assert int(counters.get("plugin_bootstrap_load_failed") or 0) == 1, counters
    assert list(plugin_status.get("statuses") or []) == [], plugin_status
    events = list(plugin_status.get("degradation_events") or [])
    assert any(str(evt.get("code") or "") == "plugin_bootstrap_load_failed" for evt in events), events
    assert all("sample" not in evt for evt in events), events
    assert "load boom" not in str(events), events
    assert plugin_status.get("telemetry_persisted") in (False, None), plugin_status
    assert isinstance(plugin_status.get("registry"), dict), plugin_status
    registry = dict(plugin_status.get("registry") or {})
    assert registry.get("capabilities") == [], plugin_status
    assert get_plugin_registry().to_dict().get("capabilities") == []
    assert isinstance(get_excel_backend(), OpenpyxlBackend)
