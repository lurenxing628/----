from __future__ import annotations

import sqlite3
from typing import List

from .batch_external_context_schema import contract_issues as batch_external_context_contract_issues
from .calendar_periods_schema import contract_issues as calendar_periods_contract_issues
from .core_schema import core_objects
from .efficiency_indexes_schema import contract_issues as efficiency_index_contract_issues
from .machine_capabilities_schema import contract_issues as machine_capabilities_contract_issues
from .material_stages_schema import contract_issues as material_stages_contract_issues
from .schema_structure import SchemaStructure
from .single_pass_indexes_schema import contract_issues as index_contract_issues
from .workbench_calibration_adoption_schema import contract_issues as calibration_adoption_contract_issues
from .workbench_dashboard_schema import workbench_dashboard_contract_issues
from .workbench_execution_ledger_schema import execution_ledger_contract_issues
from .workbench_execution_void_schema import execution_void_contract_issues
from .workbench_history_schema import workbench_history_contract_issues
from .workbench_metadata_schema import canonical_sql, workbench_metadata_contract_issues
from .workbench_outsourcing_schema import workbench_outsourcing_contract_issues
from .workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from .workbench_process_schema import workbench_process_contract_issues
from .workbench_resource_schema import workbench_resource_contract_issues
from .workbench_run_read_model_schema import contract_issues as run_read_model_contract_issues
from .workbench_run_schema import workbench_run_contract_issues
from .workbench_source_revisions_schema import source_revisions_contract_issues
from .workbench_template_lineage_schema import template_lineage_contract_issues
from .workbench_trial_schema import workbench_trial_contract_issues

CURRENT_SCHEMA_VERSION = 50


class MigrationContractError(RuntimeError):
    """Schema 契约不满足：坏库或旧版本库必须暴露，不能被当前 schema 静默补成好库。"""


def ensure_schema_version_not_older(db_version: int) -> None:
    if db_version < CURRENT_SCHEMA_VERSION:
        raise MigrationContractError(
            " ".join(
                [
                    f"检测到数据库 SchemaVersion={db_version} 低于当前程序支持版本 {CURRENT_SCHEMA_VERSION}。",
                    "系统不支持旧版数据库迁移，也不会用当前 schema.sql 静默补齐残缺结构。",
                    "请重建数据库或恢复与当前版本匹配的完整备份后再重试。",
                ]
            )
        )


def ensure_schema_version_not_newer(db_version: int) -> None:
    if db_version > CURRENT_SCHEMA_VERSION:
        raise MigrationContractError(
            " ".join(
                [
                    f"检测到数据库 SchemaVersion={db_version} 高于当前程序支持版本 {CURRENT_SCHEMA_VERSION}。",
                    "为避免旧程序破坏高版本数据库，已阻断启动/迁移。",
                    "不支持数据库降级迁移。",
                    "请升级程序或恢复兼容版本备份后再重试。",
                ]
            )
        )


def ensure_current_schema_contract(conn: sqlite3.Connection, *, schema_version: int, full_data: bool = False) -> None:
    """只用于 SchemaVersion 已等于 CURRENT_SCHEMA_VERSION 的库（启动与恢复校验、schema.sql 生成核对）。"""
    issues = current_schema_contract_issues(conn, schema_version=schema_version, full_data=full_data)
    if not issues:
        return
    visible_issues = issues[:8]
    issue_lines = [f"结构问题：{item}" for item in visible_issues]
    if len(issues) > len(visible_issues):
        issue_lines.append(f"其余结构问题 {len(issues) - len(visible_issues)} 项略。")
    raise MigrationContractError(
        " ".join(
            [
                f"检测到数据库 SchemaVersion={schema_version} 等于当前程序支持版本 {CURRENT_SCHEMA_VERSION}，但表结构不满足当前契约。",
                "为避免陈旧结构静默冒充当前版本，已阻断启动/迁移。",
                *issue_lines,
                "请恢复完整备份，或重建与当前程序版本匹配的数据库后再重试。",
            ]
        )
    )


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        # 仅在“表/列不存在”等可预期场景回落 0；其它错误必须可观测（向上抛出）
        if "no such table" in msg or "no such column" in msg:
            return 0
        raise
    if not row:
        return 0
    version = row[0]
    if type(version) is not int:
        raise MigrationContractError("数据库版本号不是整数，请恢复完整备份，或重建与当前程序版本匹配的数据库后再重试。")
    return version


def has_no_user_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table'
          AND name <> 'SchemaVersion'
          AND name NOT LIKE 'sqlite_%'
        LIMIT 1
        """
    ).fetchone()
    return row is None


def _core_schema_contract_issues(structure: SchemaStructure) -> List[str]:
    """核心表与索引按 `core_objects()` 的声明 DDL 规范化后逐字核对：列、类型、默认值、NOT NULL、CHECK、外键、
    唯一约束与索引定义都在其中，约束只从声明 DDL 读取，不另抄清单。"""
    actual = structure.sql
    return [("missing_core_schema: " if name not in actual else "bad_core_schema: ") + name
            for name, sql in core_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]


def current_schema_contract_issues(
    conn: sqlite3.Connection, *, schema_version: int, full_data: bool = False
) -> List[str]:
    """
    当前库是否满足当前版本的结构契约；生产里只由启动与恢复校验两个边界各调一次，日常事务不核 DDL。

    核心模块与各子系统 DDL 模块拥有的对象一样，按声明 DDL 规范化后逐字核对。
    """
    structure = SchemaStructure(conn)
    issues = _core_schema_contract_issues(structure)
    issues.extend(workbench_metadata_contract_issues(structure))
    issues.extend(workbench_resource_contract_issues(structure))
    issues.extend(workbench_process_contract_issues(structure))
    issues.extend(execution_ledger_contract_issues(conn, structure=structure))
    issues.extend(workbench_run_contract_issues(structure))
    issues.extend(run_read_model_contract_issues(structure))
    issues.extend(template_lineage_contract_issues(structure))
    issues.extend(workbench_trial_contract_issues(structure))
    issues.extend(workbench_history_contract_issues(structure))
    issues.extend(calibration_adoption_contract_issues(structure))
    issues.extend(workbench_dashboard_contract_issues(structure))
    # This contract already validates complete plan identities and their clock.
    issues.extend(workbench_plan_identity_contract_issues(conn, structure=structure))
    issues.extend(workbench_outsourcing_contract_issues(structure))
    issues.extend(execution_void_contract_issues(structure))
    issues.extend(batch_external_context_contract_issues(structure))
    issues.extend(calendar_periods_contract_issues(structure))
    issues.extend(machine_capabilities_contract_issues(structure))
    issues.extend(material_stages_contract_issues(structure))
    issues.extend(source_revisions_contract_issues(conn, structure=structure))
    if schema_version == CURRENT_SCHEMA_VERSION:
        issues.extend(index_contract_issues(structure))
        issues.extend(efficiency_index_contract_issues(structure))
    if full_data and structure.has_table("Schedule") and structure.has_table("ScheduleHistory"):
        issues.extend(schedule_history_data_issues(conn))
    return issues


def schedule_history_data_issues(conn):
    """Each persisted schedule version must own its historical head."""
    versions = conn.execute("SELECT DISTINCT version FROM Schedule EXCEPT SELECT version FROM ScheduleHistory LIMIT 8").fetchall()
    return ["bad_data: Schedule version=" + str(row[0]) + " missing ScheduleHistory head" for row in versions]
