from __future__ import annotations

import os
import sys
import tempfile
from unittest import mock


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema
    from web.bootstrap.plugins import bootstrap_plugins

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_plugin_bootstrap_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    plugins_dir = os.path.join(tmpdir, "plugins")
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(plugins_dir, exist_ok=True)

    ensure_schema(db_path, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=backup_dir)

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

    print("OK")


if __name__ == "__main__":
    main()
