"""回归测试：SystemConfigService.get_snapshot 遇到脏配置值（旧写法 on、越界的 0/9999、非数字 abc）时按规则归一（启用/最小1/最大365/默认60）并在 dirty_fields/dirty_reasons 标注白话原因，_dirty_field_label 对未知键回退为「系统配置项」，且 backup.html/logs.html 模板已改用 dirty_labels 渲染而非旧的 dirty_field_labels 表达式。"""

from __future__ import annotations


def test_system_config_dirty_fields_contract(db_path) -> None:
    from core.infrastructure.database import get_connection
    from core.services.system.system_config_service import SystemConfigService, _dirty_field_label

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
    assert "这个开关保存的是旧写法，本次先按“启用”处理" in str(
        dirty_reasons.get("auto_backup_enabled") or ""
    ), dirty_reasons
    assert "本次先按最小值 1 处理" in str(dirty_reasons.get("auto_backup_interval_minutes") or ""), dirty_reasons
    assert "本次先按最大值 365 处理" in str(dirty_reasons.get("auto_backup_keep_days") or ""), dirty_reasons
    assert "本次先按 60 处理" in str(dirty_reasons.get("auto_log_cleanup_interval_minutes") or ""), dirty_reasons
    assert _dirty_field_label("new_internal_config_key") == "系统配置项"

