from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .common import MigrationOutcome, merge_outcomes, table_exists

_DEFAULT_GRAPH_CONFIG: Tuple[Tuple[str, str, str], ...] = (
    ("graph_analysis_mode", "on", "工序图分析模式：关闭/只生成报告/参与排产"),
    ("graph_block_on_cycle", "no", "工序图分析发现循环依赖时是否阻止排产"),
    ("graph_critical_weight", "500", "图分析关键路径评分权重"),
    ("graph_impact_weight", "10", "图分析后续影响范围评分权重"),
    ("graph_candidate_weight_count", "5", "参与排产时额外尝试的重点工序方案档数"),
    ("graph_selection_policy", "balanced", "自动选择最终采用方案的规则"),
    ("graph_overdue_tolerance_count", "1", "综合选择时允许多出的超期批次数"),
    ("graph_tardiness_tolerance_ratio", "0.1", "综合选择时允许多出的拖期比例"),
    ("graph_debug_export", "no", "是否导出工序图分析调试文件"),
)


def _migrate_schedule_config_defaults(conn: sqlite3.Connection) -> MigrationOutcome:
    if not table_exists(conn, "ScheduleConfig"):
        return MigrationOutcome.SKIPPED

    conn.executemany(
        """
        INSERT OR IGNORE INTO ScheduleConfig(config_key, config_value, description)
        VALUES (?, ?, ?)
        """,
        _DEFAULT_GRAPH_CONFIG,
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

    defaults = {key: value for key, value, _description in _DEFAULT_GRAPH_CONFIG}
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

        changed = False
        for field, default_value in defaults.items():
            if field not in payload:
                payload[field] = default_value
                changed = True

        if changed:
            updates.append((json.dumps(payload, ensure_ascii=False, sort_keys=True), str(key)))

    if bad_keys:
        sample = "，".join(bad_keys[:20])
        raise RuntimeError(f"排产配置方案数据已损坏，请先人工修复后再迁移：{sample}") from first_exc

    if updates:
        conn.executemany(
            "UPDATE ScheduleConfig SET config_value = ? WHERE config_key = ?",
            updates,
        )
    return MigrationOutcome.APPLIED


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v9 迁移：补齐工序图分析配置字段；已有值不覆盖，缺少的字段按当前默认补齐。
    """
    outcomes = [
        _migrate_schedule_config_defaults(conn),
        _migrate_preset_payloads(conn),
    ]
    return merge_outcomes(*outcomes)
