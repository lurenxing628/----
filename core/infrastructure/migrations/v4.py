from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

from .common import MigrationOutcome, merge_outcomes
from .v4_sanitizers import _sanitize_field as _sanitize_field_impl


def _sanitize_field(
    conn: sqlite3.Connection,
    *,
    table: str,
    field: str,
    pk_expr: str,
    default: Optional[str],
    logger=None,
) -> Tuple[MigrationOutcome, int, List[str]]:
    return _sanitize_field_impl(conn, table=table, field=field, pk_expr=pk_expr, default=default, logger=logger)


def run(conn: sqlite3.Connection, logger=None) -> MigrationOutcome:
    """
    v4 迁移：统一清洗“枚举/状态类文本字段”的大小写/空格（TRIM+LOWER），并对 NULL/空串写默认值。

    目标：
    - 避免历史数据出现 INTERNAL/External/ YES 等大小写混用导致业务误判
    - 幂等：可重复执行
    - 不改表结构，仅做数据修正
    """
    tasks = [
        # Scheduler
        ("Batches", "priority", "CAST(batch_id AS TEXT)", "normal"),
        ("Batches", "ready_status", "CAST(batch_id AS TEXT)", "yes"),
        ("Batches", "status", "CAST(batch_id AS TEXT)", "pending"),
        ("BatchOperations", "source", "CAST(id AS TEXT)", "internal"),
        ("BatchOperations", "status", "CAST(id AS TEXT)", "pending"),
        ("Schedule", "lock_status", "CAST(id AS TEXT)", "unlocked"),
        ("BatchMaterials", "ready_status", "CAST(id AS TEXT)", "no"),
        # Process
        ("Parts", "route_parsed", "CAST(part_no AS TEXT)", "no"),
        ("OpTypes", "category", "CAST(op_type_id AS TEXT)", "internal"),
        ("PartOperations", "source", "CAST(id AS TEXT)", "internal"),
        ("PartOperations", "status", "CAST(id AS TEXT)", "active"),
        ("ExternalGroups", "merge_mode", "CAST(group_id AS TEXT)", "separate"),
        ("OperatorMachine", "skill_level", "CAST(id AS TEXT)", "normal"),
        ("OperatorMachine", "is_primary", "CAST(id AS TEXT)", "no"),
        # Calendar
        ("WorkCalendar", "day_type", "CAST(date AS TEXT)", "workday"),
        ("WorkCalendar", "allow_normal", "CAST(date AS TEXT)", "yes"),
        ("WorkCalendar", "allow_urgent", "CAST(date AS TEXT)", "yes"),
        (
            "OperatorCalendar",
            "day_type",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "workday",
        ),
        (
            "OperatorCalendar",
            "allow_normal",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "yes",
        ),
        (
            "OperatorCalendar",
            "allow_urgent",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "yes",
        ),
        # Master data / resources
        ("Machines", "status", "CAST(machine_id AS TEXT)", "active"),
        ("Operators", "status", "CAST(operator_id AS TEXT)", "active"),
        ("Suppliers", "status", "CAST(supplier_id AS TEXT)", "active"),
        ("Materials", "status", "CAST(material_id AS TEXT)", "active"),
        ("MachineDowntimes", "scope_type", "CAST(id AS TEXT)", "machine"),
        ("MachineDowntimes", "status", "CAST(id AS TEXT)", "active"),
    ]

    outcomes = []
    for table, field, pk_expr, default in tasks:
        outcome, _changed, _sample = _sanitize_field(
            conn, table=table, field=field, pk_expr=pk_expr, default=default, logger=logger
        )
        outcomes.append(outcome)
    return merge_outcomes(*outcomes)
