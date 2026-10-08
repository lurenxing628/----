from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional, Set

from .batch_external_context_schema import contract_issues as batch_external_context_contract_issues
from .batch_external_context_schema import objects as batch_external_context_objects
from .calendar_periods_schema import contract_issues as calendar_periods_contract_issues
from .calendar_periods_schema import objects as calendar_periods_objects
from .machine_capabilities_schema import contract_issues as machine_capabilities_contract_issues
from .machine_capabilities_schema import objects as machine_capabilities_objects
from .material_stages_schema import contract_issues as material_stages_contract_issues
from .material_stages_schema import objects as material_stages_objects
from .migration_common import MigrationOutcome, column_exists, fallback_log, table_exists
from .migration_operation_execution_contract import operation_execution_event_contract_issues
from .schema_declaration import declared_columns, load_schema_sql
from .schema_structure import SchemaStructure
from .workbench_calibration_adoption_schema import contract_issues as calibration_adoption_contract_issues
from .workbench_calibration_adoption_schema import objects as calibration_adoption_objects
from .workbench_dashboard_external_schema import contract_issues as dashboard_external_contract_issues
from .workbench_dashboard_external_schema import workbench_dashboard_external_objects
from .workbench_dashboard_schema import workbench_dashboard_contract_issues, workbench_dashboard_objects
from .workbench_execution_ledger_schema import execution_ledger_contract_issues, execution_ledger_objects
from .workbench_execution_void_schema import execution_void_contract_issues, execution_void_objects
from .workbench_lineage_lookup_schema import lineage_lookup_contract_issues, lineage_lookup_objects
from .workbench_metadata_schema import metadata_objects, workbench_metadata_contract_issues
from .workbench_outsourcing_schema import workbench_outsourcing_contract_issues, workbench_outsourcing_objects
from .workbench_outsourcing_source_schema import (
    workbench_outsourcing_source_contract_issues,
    workbench_outsourcing_source_objects,
)
from .workbench_plan_identity_schema import plan_identity_objects
from .workbench_plan_identity_write_guard import (
    plan_identity_write_guard_contract_issues,
    plan_identity_write_guard_objects,
)
from .workbench_process_schema import process_objects, workbench_process_contract_issues
from .workbench_process_workflow_schema import workbench_process_workflow_contract_issues, workflow_objects
from .workbench_resource_schema import resource_objects, workbench_resource_contract_issues
from .workbench_run_schema import workbench_run_contract_issues, workbench_run_objects
from .workbench_template_lineage_schema import template_lineage_contract_issues, template_lineage_objects
from .workbench_trial_schema import workbench_trial_contract_issues, workbench_trial_objects

CURRENT_SCHEMA_VERSION = 39


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


def ensure_current_schema_contract(
    conn: sqlite3.Connection, *, schema_version: Optional[int] = None, schema_sql: Optional[str] = None
) -> None:
    version = int(get_schema_version(conn) if schema_version is None else schema_version)
    if version == CURRENT_SCHEMA_VERSION:
        issues = current_schema_contract_issues(conn, schema_sql=schema_sql)
        if issues:
            raise build_current_schema_contract_error(version, issues=issues)


def ensure_schema_version(conn: sqlite3.Connection, logger=None, *, schema_sql: Optional[str] = None) -> None:
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
    if version <= 0 and detect_schema_is_current(conn, schema_sql=schema_sql) and is_truly_empty_db(conn):
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
        # This exact unused metadata seed is part of a fresh schema, not business data.
        if name == "WorkbenchPlanIdentityClock":
            rows = conn.execute("SELECT singleton, revision FROM WorkbenchPlanIdentityClock LIMIT 2").fetchall()
            if [tuple(row) for row in rows] != [(1, 1)]:
                return False
            continue
        if name == "WorkbenchExecutionLedgerClock":
            rows = conn.execute("SELECT singleton, revision, next_report_no FROM WorkbenchExecutionLedgerClock LIMIT 2").fetchall()
            if [tuple(row) for row in rows] != [(1, 1, 1)]:
                return False
            continue
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


def detect_schema_is_current(conn: sqlite3.Connection, *, schema_sql: Optional[str] = None) -> bool:
    return not current_schema_contract_issues(conn, schema_sql=schema_sql)


# 有自己 DDL 模块与契约函数的子系统：它们的表/索引/触发器按“DDL 逐字相等”核对，不再重复做列级比对。
_SUBSYSTEM_OBJECT_SOURCES = (
    metadata_objects, resource_objects, process_objects, workflow_objects, plan_identity_objects,
    plan_identity_write_guard_objects, execution_ledger_objects, execution_void_objects, workbench_run_objects,
    template_lineage_objects, workbench_trial_objects, lineage_lookup_objects, calibration_adoption_objects,
    workbench_dashboard_objects, workbench_dashboard_external_objects, workbench_outsourcing_objects,
    workbench_outsourcing_source_objects, batch_external_context_objects, calendar_periods_objects, machine_capabilities_objects, material_stages_objects,
)
# 有专用合并标签的核心表，不再单独报 missing_table。
_CORE_TABLES_WITH_DEDICATED_LABEL = ("SystemConfig", "SystemJobState")


def _subsystem_owned_object_names() -> Set[str]:
    owned: Set[str] = set()
    for objects in _SUBSYSTEM_OBJECT_SOURCES:
        owned.update(str(name) for name in objects())
    return owned


def _live_columns(conn: sqlite3.Connection, table: str, *, structure=None) -> Set[str]:
    quoted = '"' + str(table).replace('"', '""') + '"'
    rows = structure.table_info(table) if structure is not None else conn.execute(f"PRAGMA table_info({quoted})").fetchall()
    return {str(row[1]) for row in rows}


def current_schema_contract_issues(conn: sqlite3.Connection, *, schema_sql: Optional[str] = None) -> List[str]:
    """
    当前库是否满足当前版本的结构契约。

    核心表按“live 表列集合 ⊇ schema.sql 声明表列集合”派生比对（schema.sql 由迁移链生成，不再手写 needed 清单）；
    各子系统 DDL 模块拥有的对象交给它们自己的契约函数逐字核对。用于 brand-new 空库初始化后的版本快进与启动阻断。
    """
    issues = []
    structure = SchemaStructure(conn)
    declared: Dict[str, List[str]] = declared_columns(load_schema_sql() if schema_sql is None else schema_sql)
    owned = _subsystem_owned_object_names()
    for table, columns in declared.items():
        if table == "SchemaVersion" or table in owned or table in _CORE_TABLES_WITH_DEDICATED_LABEL:
            continue
        if not structure.has_table(table):
            issues.append(f"missing_table: {table}")
            continue
        live = _live_columns(conn, table, structure=structure)
        for col in columns:
            if col not in live:
                issues.append(f"missing_column: {table}.{col}")
    for ok, label in (
        (_has_system_management_tables(conn, structure=structure), "missing_table: SystemConfig/SystemJobState"),
        (_has_schedule_unique_index(conn, structure=structure), "bad_index: idx_schedule_version_op_unique"),
        (_has_candidate_indexes(conn, structure=structure), "bad_index: schedule candidate indexes"),
        (_has_adjustment_draft_indexes(conn, structure=structure), "bad_index: schedule adjustment draft indexes"),
        (_has_adjustment_scenario_indexes(conn, structure=structure), "bad_index: schedule adjustment scenario indexes"),
        (_batch_material_ready_default_is_no(conn, structure=structure), "bad_default: BatchMaterials.ready_status expected no"),
    ):
        if not ok:
            issues.append(label)
    issues.extend(operation_execution_event_contract_issues(conn, structure=structure))
    issues.extend(workbench_metadata_contract_issues(conn, structure=structure))
    issues.extend(workbench_resource_contract_issues(conn, structure=structure))
    issues.extend(workbench_process_contract_issues(conn, structure=structure))
    issues.extend(workbench_process_workflow_contract_issues(conn, structure=structure))
    issues.extend(execution_ledger_contract_issues(conn, structure=structure))
    issues.extend(workbench_run_contract_issues(conn, structure=structure))
    issues.extend(template_lineage_contract_issues(conn, structure=structure))
    issues.extend(workbench_trial_contract_issues(conn, structure=structure))
    issues.extend(lineage_lookup_contract_issues(conn, structure=structure))
    issues.extend(calibration_adoption_contract_issues(conn, structure=structure))
    issues.extend(workbench_dashboard_contract_issues(conn, structure=structure))
    # This contract already validates complete plan identities and their clock.
    issues.extend(plan_identity_write_guard_contract_issues(conn, structure=structure))
    issues.extend(workbench_outsourcing_contract_issues(conn, structure=structure))
    issues.extend(dashboard_external_contract_issues(conn, structure=structure))
    issues.extend(workbench_outsourcing_source_contract_issues(conn, structure=structure))
    issues.extend(execution_void_contract_issues(conn, structure=structure))
    issues.extend(batch_external_context_contract_issues(conn, structure=structure))
    issues.extend(calendar_periods_contract_issues(conn, structure=structure))
    issues.extend(machine_capabilities_contract_issues(conn, structure=structure))
    issues.extend(material_stages_contract_issues(conn, structure=structure))
    return issues


def _batch_material_ready_default_is_no(conn: sqlite3.Connection, *, structure=None) -> bool:
    try:
        rows = structure.table_info("BatchMaterials") if structure is not None else conn.execute("PRAGMA table_info(BatchMaterials)").fetchall()
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


def _has_system_management_tables(conn: sqlite3.Connection, *, structure=None) -> bool:
    structure = structure if structure is not None else SchemaStructure(conn)
    return structure.has_table("SystemConfig") and structure.has_table("SystemJobState")


def _has_schedule_unique_index(conn: sqlite3.Connection, *, structure=None) -> bool:
    structure = structure if structure is not None else SchemaStructure(conn)
    return structure.index_table("idx_schedule_version_op_unique") == "Schedule"


def _has_candidate_indexes(conn: sqlite3.Connection, *, structure=None) -> bool:
    structure = structure if structure is not None else SchemaStructure(conn)
    names = ['idx_schedule_candidate_rows_time', 'idx_schedule_candidate_rows_version_candidate', 'idx_schedule_candidate_rows_version_candidate_time', 'idx_schedule_candidate_selection_version', 'idx_schedule_candidate_version', 'idx_schedule_candidate_version_kind', 'idx_schedule_history_version', 'idx_schedule_version_time']
    return all(name in structure.objects and structure.objects[name][0] == "index" for name in names)


def _has_adjustment_draft_indexes(conn: sqlite3.Connection, *, structure=None) -> bool:
    structure = structure if structure is not None else SchemaStructure(conn)
    names = ['idx_schedule_adjustment_change_draft_op', 'idx_schedule_adjustment_draft_base', 'idx_schedule_adjustment_draft_status']
    return all(name in structure.objects and structure.objects[name][0] == "index" for name in names)


def _has_adjustment_scenario_indexes(conn: sqlite3.Connection, *, structure=None) -> bool:
    structure = structure if structure is not None else SchemaStructure(conn)
    names = ['idx_schedule_adjustment_scenario_base', 'idx_schedule_adjustment_scenario_row_op', 'idx_schedule_adjustment_scenario_row_time']
    return all(name in structure.objects and structure.objects[name][0] == "index" for name in names) and structure.has_unique_key("ScheduleAdjustmentScenario", ("source_draft_id",))
