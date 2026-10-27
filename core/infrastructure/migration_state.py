from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Dict, List, Set

from .batch_external_context_schema import contract_issues as batch_external_context_contract_issues
from .batch_external_context_schema import objects as batch_external_context_objects
from .calendar_periods_schema import contract_issues as calendar_periods_contract_issues
from .calendar_periods_schema import objects as calendar_periods_objects
from .efficiency_indexes_schema import contract_issues as efficiency_index_contract_issues
from .machine_capabilities_schema import contract_issues as machine_capabilities_contract_issues
from .machine_capabilities_schema import objects as machine_capabilities_objects
from .material_stages_schema import contract_issues as material_stages_contract_issues
from .material_stages_schema import objects as material_stages_objects
from .migration_common import fallback_log
from .schema_declaration import declared_columns
from .schema_structure import SchemaStructure
from .single_pass_indexes_schema import contract_issues as index_contract_issues
from .workbench_calibration_adoption_schema import contract_issues as calibration_adoption_contract_issues
from .workbench_calibration_adoption_schema import objects as calibration_adoption_objects
from .workbench_dashboard_external_schema import (
    workbench_dashboard_external_contract_issues as dashboard_external_contract_issues,
)
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
from .workbench_run_read_model_schema import contract_issues as run_read_model_contract_issues
from .workbench_run_read_model_schema import objects as run_read_model_objects
from .workbench_run_schema import workbench_run_contract_issues, workbench_run_objects
from .workbench_template_lineage_schema import template_lineage_contract_issues, template_lineage_objects
from .workbench_trial_schema import workbench_trial_contract_issues, workbench_trial_objects

CURRENT_SCHEMA_VERSION = 44


class MigrationContractError(RuntimeError):
    """Schema 契约不满足：坏库或旧版本库必须暴露，不能被当前 schema 静默补成好库。"""


def build_outdated_schema_version_error(
    db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION
) -> MigrationContractError:
    current = int(db_version)
    supported = int(supported_version)
    return MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={current} 低于当前程序支持版本 {supported}。",
                "系统不支持旧版数据库迁移，也不会用当前 schema.sql 静默补齐残缺结构。",
                "请重建数据库或恢复与当前版本匹配的完整备份后再重试。",
            ]
        )
    )


def build_future_schema_version_error(
    db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION
) -> MigrationContractError:
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


def build_current_schema_contract_error(db_version: int, *, issues: List[str]) -> MigrationContractError:
    current = int(db_version)
    visible_issues = issues[:8]
    issue_lines = [f"结构问题：{item}" for item in visible_issues]
    if len(issues) > len(visible_issues):
        issue_lines.append(f"其余结构问题 {len(issues) - len(visible_issues)} 项略。")
    return MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={current} 等于当前程序支持版本 {CURRENT_SCHEMA_VERSION}，但表结构不满足当前契约。",
                "为避免陈旧结构静默冒充当前版本，已阻断启动/迁移。",
                *issue_lines,
                "请恢复完整备份，或重建与当前程序版本匹配的数据库后再重试。",
            ]
        )
    )


def ensure_schema_version_not_newer(db_version: int, *, supported_version: int = CURRENT_SCHEMA_VERSION) -> None:
    if int(db_version) > int(supported_version):
        raise build_future_schema_version_error(int(db_version), supported_version=int(supported_version))


def ensure_current_schema_contract(
    conn: sqlite3.Connection, *, schema_version: int, schema_sql: str, full_data: bool = False
) -> None:
    version = int(schema_version)
    if version == CURRENT_SCHEMA_VERSION:
        issues = current_schema_contract_issues(conn, schema_version=version, schema_sql=schema_sql, full_data=full_data)
        if issues:
            raise build_current_schema_contract_error(version, issues=issues)


def ensure_schema_version(
    conn: sqlite3.Connection, logger=None, *, schema_sql: str, full_data: bool = False
) -> int:
    """
    若当前为空库且结构已满足当前版本契约，则确保 SchemaVersion 表存在并将版本号设为 CURRENT_SCHEMA_VERSION；
    否则不执行任何写入，原样返回当前版本号。
    """
    version = get_schema_version(conn)
    if version <= 0 and is_truly_empty_db(conn) and detect_schema_is_current(
        conn, schema_version=version, schema_sql=schema_sql, full_data=full_data
    ):
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
        set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        fallback_log(
            logger, "info", f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。"
        )
        return CURRENT_SCHEMA_VERSION
    return version


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if not row:
            return 0
        return int(row[0])
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
    return [r[0] for r in rows]


def has_no_user_tables(conn: sqlite3.Connection) -> bool:
    return len(list_user_tables(conn)) == 0


def detect_schema_is_current(
    conn: sqlite3.Connection, *, schema_version: int, schema_sql: str, full_data: bool = False
) -> bool:
    return not current_schema_contract_issues(conn, schema_version=schema_version, schema_sql=schema_sql, full_data=full_data)


# 有自己 DDL 模块与契约函数的子系统：它们的表/索引/触发器按“DDL 逐字相等”核对，不再重复做列级比对。
_SUBSYSTEM_OBJECT_SOURCES = (
    metadata_objects, resource_objects, process_objects, workflow_objects, plan_identity_objects,
    plan_identity_write_guard_objects, execution_ledger_objects, execution_void_objects, workbench_run_objects, run_read_model_objects,
    template_lineage_objects, workbench_trial_objects, lineage_lookup_objects, calibration_adoption_objects,
    workbench_dashboard_objects, workbench_dashboard_external_objects, workbench_outsourcing_objects,
    workbench_outsourcing_source_objects, batch_external_context_objects, calendar_periods_objects, machine_capabilities_objects, material_stages_objects,
)
# 有专用合并标签的核心表，不再单独报 missing_table。
_CORE_TABLES_WITH_DEDICATED_LABEL = ("SystemConfig", "SystemJobState")


@lru_cache(maxsize=1)
def _subsystem_owned_object_names() -> Set[str]:
    owned: Set[str] = set()
    for objects in _SUBSYSTEM_OBJECT_SOURCES:
        owned.update(str(name) for name in objects())
    return owned


def current_schema_contract_issues(
    conn: sqlite3.Connection, *, schema_version: int, schema_sql: str, full_data: bool = False
) -> List[str]:
    """
    当前库是否满足当前版本的结构契约。

    核心表按“live 表列集合 ⊇ schema.sql 声明表列集合”派生比对；
    各子系统 DDL 模块拥有的对象交给它们自己的契约函数逐字核对。用于 brand-new 空库初始化后的版本快进与启动阻断。
    """
    issues = []
    structure = SchemaStructure(conn)
    declared: Dict[str, List[str]] = declared_columns(schema_sql)
    owned = _subsystem_owned_object_names()
    for table, columns in declared.items():
        if table == "SchemaVersion" or table in owned or table in _CORE_TABLES_WITH_DEDICATED_LABEL:
            continue
        if not structure.has_table(table):
            issues.append(f"missing_table: {table}")
            continue
        live = {row[1] for row in structure.table_info(table)}
        for col in columns:
            if col not in live:
                issues.append(f"missing_column: {table}.{col}")
    for ok, label in (
        (_has_system_management_tables(structure=structure), "missing_table: SystemConfig/SystemJobState"),
        (_has_schedule_unique_index(structure=structure), "bad_index: idx_schedule_version_op_unique"),
        (_batch_material_ready_default_is_no(structure=structure), "bad_default: BatchMaterials.ready_status expected no"),
    ):
        if not ok:
            issues.append(label)
    issues.extend(workbench_metadata_contract_issues(conn, structure=structure))
    issues.extend(workbench_resource_contract_issues(conn, structure=structure))
    issues.extend(workbench_process_contract_issues(conn, structure=structure))
    issues.extend(workbench_process_workflow_contract_issues(conn, structure=structure))
    issues.extend(execution_ledger_contract_issues(conn, structure=structure))
    issues.extend(workbench_run_contract_issues(conn, structure=structure))
    issues.extend(run_read_model_contract_issues(conn, structure=structure))
    issues.extend(template_lineage_contract_issues(conn, structure=structure))
    issues.extend(workbench_trial_contract_issues(conn, structure=structure))
    issues.extend(lineage_lookup_contract_issues(structure))
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
    if schema_version in (0, CURRENT_SCHEMA_VERSION):
        issues.extend(index_contract_issues(conn, structure=structure))
        issues.extend(efficiency_index_contract_issues(conn, structure=structure))
    if full_data and structure.has_table("Schedule") and structure.has_table("ScheduleHistory"):
        issues.extend(schedule_history_data_issues(conn))
    return issues


def schedule_history_data_issues(conn):
    """Each persisted schedule version must own its historical head."""
    versions = conn.execute("SELECT DISTINCT version FROM Schedule EXCEPT SELECT version FROM ScheduleHistory LIMIT 8").fetchall()
    return ["bad_data: Schedule version=" + str(row[0]) + " missing ScheduleHistory head" for row in versions]


def _batch_material_ready_default_is_no(*, structure: SchemaStructure) -> bool:
    for row in structure.table_info("BatchMaterials"):
        name = row[1]
        if name != "ready_status":
            continue
        default_value = row[4]
        normalized = str(default_value or "").strip().strip("'\"").lower()
        return normalized == "no"
    return False


def _has_system_management_tables(*, structure: SchemaStructure) -> bool:
    return structure.has_table("SystemConfig") and structure.has_table("SystemJobState")


def _has_schedule_unique_index(*, structure: SchemaStructure) -> bool:
    return (
        structure.index_table("idx_schedule_version_op_unique") == "Schedule"
        and structure.has_unique_key("Schedule", ("version", "op_id"))
        and any(
            row[1] == "idx_schedule_version_op_unique"
            and row[2]
            and not row[4]
            and tuple(col[2] for col in structure.index_info(row[1])) == ("version", "op_id")
            for row in structure.index_list("Schedule")
        )
    )
