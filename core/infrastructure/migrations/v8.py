from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .common import MigrationOutcome, merge_outcomes, table_exists


def _update_if_table_exists(conn: sqlite3.Connection, table: str, sql: str, params: Tuple[Any, ...] = ()) -> MigrationOutcome:
    if not table_exists(conn, table):
        return MigrationOutcome.SKIPPED
    conn.execute(sql, params)
    return MigrationOutcome.APPLIED


def _migrate_batches(conn: sqlite3.Connection) -> MigrationOutcome:
    return _update_if_table_exists(
        conn,
        "Batches",
        """
        UPDATE Batches
        SET ready_status = 'yes',
            ready_date = NULL
        """,
    )


def _migrate_batch_materials(conn: sqlite3.Connection) -> MigrationOutcome:
    return _update_if_table_exists(
        conn,
        "BatchMaterials",
        """
        UPDATE BatchMaterials
        SET available_qty = CASE
                WHEN available_qty IS NULL OR available_qty < required_qty THEN required_qty
                ELSE available_qty
            END,
            ready_status = 'yes'
        WHERE required_qty IS NOT NULL
        """,
    )


def _migrate_enforce_ready_default(conn: sqlite3.Connection) -> MigrationOutcome:
    return _update_if_table_exists(
        conn,
        "ScheduleConfig",
        """
        UPDATE ScheduleConfig
        SET config_value = 'no'
        WHERE config_key = 'enforce_ready_default'
        """,
    )


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

    bad_keys: List[str] = []
    updates: List[Tuple[str, str]] = []
    first_exc: Optional[Exception] = None
    for row in rows:
        key = row["config_key"] if isinstance(row, sqlite3.Row) else row[0]
        raw = row["config_value"] if isinstance(row, sqlite3.Row) else row[1]
        try:
            payload = _load_preset_payload(raw, key=str(key))
        except RuntimeError as exc:
            bad_keys.append(str(key))
            if first_exc is None:
                first_exc = exc
            continue
        if str(payload.get("enforce_ready_default") or "") == "no":
            continue
        payload["enforce_ready_default"] = "no"
        updates.append((json.dumps(payload, ensure_ascii=False, sort_keys=True), str(key)))

    if bad_keys:
        sample = "，".join(bad_keys[:20])
        raise RuntimeError(f"排产配置方案数据已损坏，请先人工修复后再迁移：{sample}") from first_exc

    conn.executemany(
        "UPDATE ScheduleConfig SET config_value = ? WHERE config_key = ?",
        updates,
    )
    return MigrationOutcome.APPLIED


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v8 迁移：把历史数据切到“齐套功能保留，但默认不生效”的业务口径。

    目标：
    - 已有批次默认齐套，齐套日期清空
    - 已有物料需求默认到齐，且保留已经超过需求数量的到料记录
    - 默认排产配置和自定义方案都关闭齐套检查
    """
    outcomes = [
        _migrate_batches(conn),
        _migrate_batch_materials(conn),
        _migrate_enforce_ready_default(conn),
        _migrate_preset_payloads(conn),
    ]
    return merge_outcomes(*outcomes)
