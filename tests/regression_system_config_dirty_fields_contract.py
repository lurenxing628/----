from __future__ import annotations

import os
import sys
import tempfile


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

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system.system_config_service import SystemConfigService

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_system_cfg_dirty_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(db_path, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=backup_dir)

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO SystemConfig (config_key, config_value, description) VALUES (?, ?, ?)",
            ("auto_backup_enabled", "on", "dirty yes/no"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO SystemConfig (config_key, config_value, description) VALUES (?, ?, ?)",
            ("auto_backup_interval_minutes", "0", "dirty interval"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO SystemConfig (config_key, config_value, description) VALUES (?, ?, ?)",
            ("auto_backup_keep_days", "9999", "dirty keep days"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO SystemConfig (config_key, config_value, description) VALUES (?, ?, ?)",
            ("auto_log_cleanup_interval_minutes", "abc", "dirty log interval"),
        )
        conn.commit()

        snapshot = SystemConfigService(conn).get_snapshot(backup_keep_days_default=30)
        data = snapshot.to_dict()
    finally:
        conn.close()

    assert snapshot.auto_backup_enabled == "yes", snapshot
    assert snapshot.auto_backup_interval_minutes == 1, snapshot
    assert snapshot.auto_backup_keep_days == 365, snapshot
    assert snapshot.auto_log_cleanup_interval_minutes == 60, snapshot

    dirty_fields = set(data.get("dirty_fields") or [])
    expected_dirty = {
        "auto_backup_enabled",
        "auto_backup_interval_minutes",
        "auto_backup_keep_days",
        "auto_log_cleanup_interval_minutes",
    }
    assert expected_dirty.issubset(dirty_fields), data

    dirty_reasons = dict(data.get("dirty_reasons") or {})
    assert "兼容归一为 yes" in str(dirty_reasons.get("auto_backup_enabled") or ""), dirty_reasons
    assert "已钳制为 1" in str(dirty_reasons.get("auto_backup_interval_minutes") or ""), dirty_reasons
    assert "已钳制为 365" in str(dirty_reasons.get("auto_backup_keep_days") or ""), dirty_reasons
    assert "已回退为 60" in str(dirty_reasons.get("auto_log_cleanup_interval_minutes") or ""), dirty_reasons

    print("OK")


if __name__ == "__main__":
    main()
