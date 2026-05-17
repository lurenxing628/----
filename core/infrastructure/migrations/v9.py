from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .common import MigrationOutcome, merge_outcomes, table_exists

_GRAPH_CONFIG_DEFAULTS: Tuple[Tuple[str, Any, str], ...] = (
    ("graph_analysis_mode", "off", "工序图分析模式：off/report/on；当前默认关闭"),
    ("graph_block_on_cycle", "no", "工序图分析发现环时是否阻止排产"),
    ("graph_critical_weight", 500, "工序图关键路径评分权重"),
    ("graph_impact_weight", 10, "工序图后续影响范围评分权重"),
    ("graph_debug_export", "no", "是否输出工序图分析调试文件"),
)


def _config_key(row: Any) -> str:
    return str(row["config_key"] if isinstance(row, sqlite3.Row) else row[0])


def _config_value(row: Any) -> Any:
    return row["config_value"] if isinstance(row, sqlite3.Row) else row[1]


def _insert_missing_defaults(conn: sqlite3.Connection) -> MigrationOutcome:
    if not table_exists(conn, "ScheduleConfig"):
        return MigrationOutcome.SKIPPED

    existing_rows = conn.execute("SELECT config_key FROM ScheduleConfig").fetchall()
    existing = {_config_key(row) for row in existing_rows}
    inserts = [(key, value, description) for key, value, description in _GRAPH_CONFIG_DEFAULTS if key not in existing]
    if inserts:
        conn.executemany(
            """
            INSERT INTO ScheduleConfig(config_key, config_value, description)
            VALUES (?, ?, ?)
            """,
            inserts,
        )
    return MigrationOutcome.APPLIED


def _load_preset_payload(raw: Any, *, key: str) -> Dict[str, Any]:
    try:
        data = json.loads(str(raw))
    except Exception as exc:
        raise RuntimeError(f"排产配置方案数据已损坏，请先人工修复后再迁移：{key}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"排产配置方案数据已损坏，请先人工修复后再迁移：{key}")
    return dict(data)


def _migrate_preset_payloads(conn: sqlite3.Connection) -> MigrationOutcome:
    if not table_exists(conn, "ScheduleConfig"):
        return MigrationOutcome.SKIPPED

    rows = conn.execute(
        """
        SELECT config_key, config_value
        FROM ScheduleConfig
        WHERE config_key LIKE 'preset.%'
        ORDER BY config_key
        """
    ).fetchall()
    if not rows:
        return MigrationOutcome.APPLIED

    defaults = {key: value for key, value, _description in _GRAPH_CONFIG_DEFAULTS}
    bad_keys: List[str] = []
    updates: List[Tuple[str, str]] = []
    first_exc: Optional[Exception] = None
    for row in rows:
        key = _config_key(row)
        try:
            payload = _load_preset_payload(_config_value(row), key=key)
        except RuntimeError as exc:
            bad_keys.append(key)
            if first_exc is None:
                first_exc = exc
            continue

        changed = False
        for config_key, default_value in defaults.items():
            if config_key not in payload:
                payload[config_key] = default_value
                changed = True
        if changed:
            updates.append((json.dumps(payload, ensure_ascii=False, sort_keys=True), key))

    if bad_keys:
        sample = "，".join(bad_keys[:20])
        raise RuntimeError(f"排产配置方案数据已损坏，请先人工修复后再迁移：{sample}") from first_exc

    if updates:
        conn.executemany("UPDATE ScheduleConfig SET config_value = ? WHERE config_key = ?", updates)
    return MigrationOutcome.APPLIED


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """v9: add optional scheduler graph analysis config defaults and preset fields."""
    outcomes = [
        _insert_missing_defaults(conn),
        _migrate_preset_payloads(conn),
    ]
    return merge_outcomes(*outcomes)


__all__ = ["run"]
