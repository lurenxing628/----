from __future__ import annotations

import sqlite3
from typing import List, Optional

from .migration_operation_execution_contract import operation_execution_event_contract_issues
from .migrations.common import MigrationOutcome, column_exists, fallback_log, table_exists

CURRENT_SCHEMA_VERSION = 19


class MigrationContractError(RuntimeError):
    """迁移契约不满足：坏库必须暴露，不能被当前 schema 静默补成好库。"""


def build_contract_error(
    *,
    missing_tables: Optional[List[str]] = None,
    blocked_version: Optional[int] = None,
    blocked_outcome: Optional[MigrationOutcome] = None,
    bootstrap_error: Optional[Exception] = None,
) -> MigrationContractError:
    parts = ["检测到非空数据库存在不受支持的残缺结构。"]
    if missing_tables:
        parts.append(f"已识别缺失整表：{', '.join(missing_tables)}。")
    parts.append("系统不会用当前 schema.sql 静默补齐缺失整表；请先人工修复或恢复到完整备份后再重试。")
    if bootstrap_error is not None:
        parts.append(f"缺失整表预补齐失败：{bootstrap_error}")
    elif blocked_version is not None and blocked_outcome is not None:
        parts.append(f"迁移预检在 v{blocked_version} 返回 {blocked_outcome.value}。")
    return MigrationContractError(" ".join(parts))


def build_future_schema_version_error(db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION) -> MigrationContractError:
    current = int(db_version)
    supported = int(supported_version)
    return MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={current} 高于当前程序支持版本 {supported}。",
                "为避免旧程序破坏高版本数据库，已阻断启动/迁移。",
                "不支持数据库降级迁移。",
                "请升级程序或恢复兼容版本备份后再重试。",
            ]
        )
    )


def build_current_schema_contract_error(
    db_version: int,
    *,
    supported_version: int = CURRENT_SCHEMA_VERSION,
    issues: Optional[List[str]] = None,
) -> MigrationContractError:
    current = int(db_version)
    supported = int(supported_version)
    visible_issues = _prioritized_contract_issues(issues or [])
    issue_lines = [f"结构问题：{item}" for item in visible_issues]
    if issues and len(issues) > len(visible_issues):
        issue_lines.append(f"其余结构问题 {len(issues) - len(visible_issues)} 项略。")
    return MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={current} 等于当前程序支持版本 {supported}，但表结构不满足当前契约。",
                "为避免陈旧结构静默冒充当前版本，已阻断启动/迁移。",
                *issue_lines,
                "请恢复完整备份，或先使用能正确迁移该数据库的程序版本修复结构后再重试。",
            ]
        )
    )


def _prioritized_contract_issues(issues: List[str]) -> List[str]:
    operation_issues = [item for item in issues if "OperationExecutionEvents" in item or "__probe_" in item]
    other_issues = [item for item in issues if item not in operation_issues]
    return (operation_issues + other_issues)[:8]


def ensure_schema_version_not_newer(db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION) -> None:
    if int(db_version) > int(supported_version):
        raise build_future_schema_version_error(int(db_version), supported_version=int(supported_version))


def ensure_current_schema_contract(conn: sqlite3.Connection, *, schema_version: Optional[int] = None) -> None:
    version = int(get_schema_version(conn) if schema_version is None else schema_version)
    if version == CURRENT_SCHEMA_VERSION:
        issues = current_schema_contract_issues(conn)
        if issues:
            raise build_current_schema_contract_error(version, issues=issues)


def ensure_schema_version(conn: sqlite3.Connection, logger=None) -> None:
    """
    确保 SchemaVersion 表存在，并写入/修正版本号。

    兼容策略：
    - 老库可能没有 SchemaVersion：插入 version=0
    - 新库可能由 schema.sql 初始化为 version=0：若检测到结构已满足当前版本且库中仍无业务数据，则直接将版本提升到 CURRENT_SCHEMA_VERSION
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0)")

    version = get_schema_version(conn)
    if version <= 0 and detect_schema_is_current(conn) and is_truly_empty_db(conn):
        set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        if logger:
            fallback_log(
                logger, "info", f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。"
            )


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if not row:
            return 0
        return int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        # 仅在“表/列不存在”等可预期场景回落 0；其它错误必须可观测（向上抛出）
        if "no such table" in msg or "no such column" in msg:
            return 0
        raise


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (int(version),))


def is_truly_empty_db(conn: sqlite3.Connection) -> bool:
    for name in list_user_tables(conn):
        quoted_name = '"' + str(name).replace('"', '""') + '"'
        row = conn.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1").fetchone()
        if row is not None:
            return False
    return True


def list_user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name <> 'SchemaVersion'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]


def has_no_user_tables(conn: sqlite3.Connection) -> bool:
    return len(list_user_tables(conn)) == 0


def detect_schema_is_current(conn: sqlite3.Connection) -> bool:
    return not current_schema_contract_issues(conn)


def current_schema_contract_issues(conn: sqlite3.Connection) -> List[str]:
    """
    用“结构特征”判断当前 DB 是否已经包含当前 schema.sql 的关键字段，
    用于 brand-new 空库初始化后的版本快进。
    """
    issues = []
    needed = [
        ("ResourceTeams", "team_id"),
        ("Operators", "team_id"),
        ("Machines", "category"),
        ("Machines", "team_id"),
        ("Batches", "ready_date"),
        ("MachineDowntimes", "scope_type"),
        ("MachineDowntimes", "scope_value"),
        ("WorkCalendar", "shift_start"),
        ("WorkCalendar", "shift_end"),
        ("OperatorCalendar", "operator_id"),
        ("OperatorMachine", "skill_level"),
        ("OperatorMachine", "is_primary"),
        ("ScheduleCandidate", "candidate_key"),
        ("ScheduleCandidate", "status"),
        ("ScheduleCandidateRows", "candidate_id"),
        ("ScheduleCandidateSelection", "source_table"),
        ("ScheduleVersionSeq", "version"),
        ("ScheduleAdjustmentDraft", "draft_id"),
        ("ScheduleAdjustmentChange", "draft_id"),
        ("ScheduleAdjustmentScenario", "scenario_id"),
        ("ScheduleAdjustmentScenario", "published_version"),
        ("ScheduleAdjustmentScenario", "published_by"),
        ("ScheduleAdjustmentScenario", "published_reason"),
        ("ScheduleAdjustmentScenario", "published_at"),
        ("ScheduleAdjustmentScenario", "execution_snapshot_revision"),
        ("ScheduleAdjustmentScenario", "execution_snapshot_op_ids"),
        ("ScheduleAdjustmentScenario", "execution_snapshot_op_count"),
        ("ScheduleAdjustmentScenarioRow", "scenario_id"),
        ("OperationExecutionEvents", "id"),
        ("OperationExecutionEvents", "schedule_version"),
        ("OperationExecutionEvents", "schedule_id"),
        ("OperationExecutionEvents", "op_id"),
        ("OperationExecutionEvents", "batch_id"),
        ("OperationExecutionEvents", "source_table"),
        ("OperationExecutionEvents", "effective_plan_role"),
        ("OperationExecutionEvents", "scenario_id"),
        ("OperationExecutionEvents", "event_type"),
        ("OperationExecutionEvents", "reported_status"),
        ("OperationExecutionEvents", "event_time"),
        ("OperationExecutionEvents", "actual_machine_id"),
        ("OperationExecutionEvents", "actual_operator_id"),
        ("OperationExecutionEvents", "quantity_done"),
        ("OperationExecutionEvents", "quantity_scrapped"),
        ("OperationExecutionEvents", "reason_code"),
        ("OperationExecutionEvents", "reason_detail"),
        ("OperationExecutionEvents", "severity"),
        ("OperationExecutionEvents", "impact_minutes"),
        ("OperationExecutionEvents", "affected_machine_id"),
        ("OperationExecutionEvents", "affected_operator_id"),
        ("OperationExecutionEvents", "handling_status"),
        ("OperationExecutionEvents", "suggest_reschedule"),
        ("OperationExecutionEvents", "remark"),
        ("OperationExecutionEvents", "created_by"),
        ("OperationExecutionEvents", "idempotency_key"),
        ("OperationExecutionEvents", "request_fingerprint"),
        ("OperationExecutionEvents", "previous_state_revision"),
        ("OperationExecutionEvents", "created_at"),
    ]
    missing_tables = set()
    for table, col in needed:
        if table in missing_tables:
            continue
        if not table_exists(conn, table):
            issues.append(f"missing_table: {table}")
            missing_tables.add(table)
            continue
        if not column_exists(conn, table, col):
            issues.append(f"missing_column: {table}.{col}")
    for ok, label in (
        (_has_system_management_tables(conn), "missing_table: SystemConfig/SystemJobState"),
        (_has_schedule_unique_index(conn), "bad_index: idx_schedule_version_op_unique"),
        (_has_candidate_indexes(conn), "bad_index: schedule candidate indexes"),
        (_has_adjustment_draft_indexes(conn), "bad_index: schedule adjustment draft indexes"),
        (_has_adjustment_scenario_indexes(conn), "bad_index: schedule adjustment scenario indexes"),
        (_batch_material_ready_default_is_no(conn), "bad_default: BatchMaterials.ready_status expected no"),
    ):
        if not ok:
            issues.append(label)
    issues.extend(operation_execution_event_contract_issues(conn))
    return issues


def _batch_material_ready_default_is_no(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("PRAGMA table_info(BatchMaterials)").fetchall()
    except sqlite3.OperationalError:
        return False
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        if name != "ready_status":
            continue
        default_value = row["dflt_value"] if isinstance(row, sqlite3.Row) else row[4]
        normalized = str(default_value or "").strip().strip("'\"").lower()
        return normalized == "no"
    return False


def _has_system_management_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('SystemConfig','SystemJobState')"
    ).fetchall()
    names = {r[0] if not isinstance(r, sqlite3.Row) else r["name"] for r in row}
    return "SystemConfig" in names and "SystemJobState" in names


def _has_schedule_unique_index(conn: sqlite3.Connection) -> bool:
    index_row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='index'
          AND name='idx_schedule_version_op_unique'
          AND tbl_name='Schedule'
        LIMIT 1
        """
    ).fetchone()
    return index_row is not None


def _has_candidate_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_version_time',
                  'idx_schedule_history_version',
                  'idx_schedule_candidate_version',
                  'idx_schedule_candidate_version_kind',
                  'idx_schedule_candidate_rows_version_candidate',
                  'idx_schedule_candidate_rows_version_candidate_time',
                  'idx_schedule_candidate_rows_time',
                  'idx_schedule_candidate_selection_version'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_version_time",
        "idx_schedule_history_version",
        "idx_schedule_candidate_version",
        "idx_schedule_candidate_version_kind",
        "idx_schedule_candidate_rows_version_candidate",
        "idx_schedule_candidate_rows_version_candidate_time",
        "idx_schedule_candidate_rows_time",
        "idx_schedule_candidate_selection_version",
    }


def _has_adjustment_draft_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_adjustment_draft_base',
                  'idx_schedule_adjustment_draft_status',
                  'idx_schedule_adjustment_change_draft_op'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_adjustment_draft_base",
        "idx_schedule_adjustment_draft_status",
        "idx_schedule_adjustment_change_draft_op",
    }


def _has_adjustment_scenario_indexes(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
              AND name IN (
                  'idx_schedule_adjustment_scenario_base',
                  'idx_schedule_adjustment_scenario_draft',
                  'idx_schedule_adjustment_scenario_row_op',
                  'idx_schedule_adjustment_scenario_row_time'
              )
        """
    ).fetchall()
    names = {r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows}
    return names == {
        "idx_schedule_adjustment_scenario_base",
        "idx_schedule_adjustment_scenario_draft",
        "idx_schedule_adjustment_scenario_row_op",
        "idx_schedule_adjustment_scenario_row_time",
    }
