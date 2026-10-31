"""Unified source revision sets and single-query reader for workbench snapshots."""

from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Tuple

from core.infrastructure.workbench_source_revisions_schema import select_source_revisions


def _unique_keys(*groups: Iterable[str]) -> Tuple[str, ...]:
    merged: List[str] = []
    for group in groups:
        merged.extend(group)
    return tuple(dict.fromkeys(merged))


# 批次领域：依赖 schedule_references（仅 op_id/version 变化或增删才推进，仅改排期时间不推进），不含 schedule_rows 与 workbench_plan_identity
BATCH_SOURCE_KEYS: Tuple[str, ...] = (
    "batches",
    "batch_operations",
    "batch_external_contexts",
    "batch_materials",
    "batch_material_reviews",
    "batch_material_stages",
    "batch_material_arrivals",
    "batch_quantity_splits",
    "parts",
    "part_operations",
    "external_groups",
    "materials",
    "machines",
    "machine_op_types",
    "operators",
    "operator_machines",
    "operator_skills",
    "op_types",
    "suppliers",
    "workbench_supplier_op_types",
    "workbench_supplier_profiles",
    "workbench_operator_profiles",
    "workbench_machine_groups",
    "workbench_machine_group_members",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
    "workbench_op_type_policies",
    "workbench_entity_refs",
    "workbench_process_workflow",
    "workbench_process_operation_confirmations",
    "workbench_template_lineage",
    "outsourcing",
    "execution_ledger",
    "schedule_references",
    "schedule_history",
    "production_input_receipts",
)

# 工艺共享字典（单零件作用域时与目标零件闭包组合，不含 parts/part_operations/external_groups/workbench_entity_refs 以免被无关零件修改污染）
PROCESS_SHARED_DICTIONARY_KEYS: Tuple[str, ...] = (
    "op_types",
    "suppliers",
    "workbench_supplier_profiles",
    "workbench_supplier_op_types",
    "workbench_op_type_policies",
    "machines",
    "machine_op_types",
    "operators",
    "operator_skills",
    "operator_machines",
    "workbench_operator_profiles",
    "workbench_machine_groups",
    "workbench_machine_group_members",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
)

# 工艺全量作用域
PROCESS_SOURCE_KEYS: Tuple[str, ...] = _unique_keys(
    PROCESS_SHARED_DICTIONARY_KEYS,
    (
        "parts",
        "part_operations",
        "external_groups",
        "batches",
        "batch_operations",
        "batch_external_contexts",
        "workbench_process_workflow",
        "workbench_process_operation_confirmations",
        "workbench_entity_refs",
        "workbench_template_lineage",
    ),
)

# 物料领域
MATERIAL_SOURCE_KEYS: Tuple[str, ...] = (
    "materials",
    "batch_materials",
    "batch_material_reviews",
    "batch_material_stages",
    "batch_material_arrivals",
    "batch_quantity_splits",
    "batches",
    "workbench_entity_refs",
)

# 资源领域（含班表时段 workbench_shift_day_periods、停机、执行台账等）
RESOURCE_SOURCE_KEYS: Tuple[str, ...] = (
    "op_types",
    "machines",
    "machine_op_types",
    "machine_downtimes",
    "operators",
    "operator_skills",
    "operator_machines",
    "suppliers",
    "resource_teams",
    "workbench_operator_profiles",
    "workbench_supplier_op_types",
    "workbench_supplier_profiles",
    "workbench_machine_groups",
    "workbench_machine_group_members",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
    "workbench_shift_day_periods",
    "workbench_op_type_policies",
    "workbench_entity_refs",
    "work_calendar",
    "operator_calendar",
    "workbench_calendar_defaults",
    "parts",
    "part_operations",
    "external_groups",
    "workbench_process_workflow",
    "workbench_process_operation_confirmations",
    "batches",
    "batch_operations",
    "materials",
    "schedule_rows",
    "schedule_references",
    "execution_ledger",
)

# 日历与人员日历领域
CALENDAR_SOURCE_KEYS: Tuple[str, ...] = (
    "work_calendar",
    "workbench_calendar_defaults",
    "workbench_entity_refs",
)

OPERATOR_CALENDAR_SOURCE_KEYS: Tuple[str, ...] = (
    "operator_calendar",
    "operators",
    "workbench_operator_profiles",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
    "workbench_shift_day_periods",
    "work_calendar",
    "workbench_calendar_defaults",
    "workbench_entity_refs",
)

# 主数据总览领域
MASTER_OVERVIEW_SOURCE_KEYS: Tuple[str, ...] = (
    "parts",
    "part_operations",
    "external_groups",
    "op_types",
    "machines",
    "machine_op_types",
    "operators",
    "operator_skills",
    "operator_machines",
    "materials",
    "suppliers",
    "work_calendar",
    "operator_calendar",
    "resource_teams",
    "workbench_operator_profiles",
    "workbench_supplier_op_types",
    "workbench_supplier_profiles",
    "workbench_machine_groups",
    "workbench_machine_group_members",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
    "workbench_shift_day_periods",
    "workbench_calendar_defaults",
    "workbench_op_type_policies",
    "workbench_entity_refs",
    "batches",
    "batch_materials",
    "batch_material_arrivals",
    "batch_material_reviews",
    "batch_material_stages",
    "batch_quantity_splits",
    "workbench_process_workflow",
    "workbench_process_operation_confirmations",
)

# 外协领域
OUTSOURCING_SOURCE_KEYS: Tuple[str, ...] = (
    "outsourcing",
    "batches",
    "batch_operations",
    "batch_external_contexts",
    "parts",
    "part_operations",
    "external_groups",
    "suppliers",
    "workbench_supplier_op_types",
    "workbench_supplier_profiles",
    "op_types",
    "workbench_op_type_policies",
    "workbench_entity_refs",
    "workbench_plan_identity",
)

# 预检领域（覆盖 ProductionFactsCapture 读取的全部生产输入表 + system_config + production_input_receipts；
# 严格不含 scheduling_preferences、run_jobs、trial_records、dashboard_handling）
PREFLIGHT_SOURCE_KEYS: Tuple[str, ...] = (
    "parts",
    "part_operations",
    "external_groups",
    "op_types",
    "machines",
    "machine_op_types",
    "machine_downtimes",
    "operators",
    "operator_skills",
    "operator_machines",
    "materials",
    "suppliers",
    "work_calendar",
    "operator_calendar",
    "resource_teams",
    "workbench_operator_profiles",
    "workbench_supplier_op_types",
    "workbench_supplier_profiles",
    "workbench_machine_groups",
    "workbench_machine_group_members",
    "workbench_shift_profiles",
    "workbench_shift_pattern_days",
    "workbench_shift_day_periods",
    "workbench_calendar_defaults",
    "workbench_op_type_policies",
    "workbench_entity_refs",
    "batches",
    "batch_operations",
    "batch_external_contexts",
    "batch_materials",
    "batch_material_reviews",
    "batch_material_stages",
    "batch_material_arrivals",
    "batch_quantity_splits",
    "workbench_process_workflow",
    "workbench_process_operation_confirmations",
    "workbench_template_lineage",
    "schedule_rows",
    "schedule_references",
    "schedule_history",
    "schedule_version_seq",
    "schedule_config",
    "system_config",
    "workbench_plan_identity",
    "execution_ledger",
    "outsourcing",
    "calibration_adoptions",
    "dashboard_items",
    "production_input_receipts",
)

# 试调领域（PREFLIGHT_SOURCE_KEYS + trial_records + trial_adoption_receipts + run_jobs + schedule_rows + schedule_history）
TRIAL_SOURCE_KEYS: Tuple[str, ...] = _unique_keys(
    PREFLIGHT_SOURCE_KEYS,
    (
        "trial_records",
        "trial_adoption_receipts",
        "run_jobs",
        "schedule_rows",
        "schedule_history",
    ),
)

# 计划领域（覆盖计划、批次、工艺、资源、日历、停机、采纳证据等）
PLAN_SOURCE_KEYS: Tuple[str, ...] = _unique_keys(
    PREFLIGHT_SOURCE_KEYS,
    (
        "run_jobs",
        "trial_records",
        "trial_adoption_receipts",
    ),
)

# 看板领域
DASHBOARD_SOURCE_KEYS: Tuple[str, ...] = _unique_keys(
    PLAN_SOURCE_KEYS,
    (
        "dashboard_items",
        "dashboard_handling",
    ),
)

# 执行与实际甘特领域
EXECUTION_SOURCE_KEYS: Tuple[str, ...] = PLAN_SOURCE_KEYS

# 报表与报表目录领域
REPORT_SOURCE_KEYS: Tuple[str, ...] = PLAN_SOURCE_KEYS
REPORT_CATALOG_SOURCE_KEYS: Tuple[str, ...] = PLAN_SOURCE_KEYS

# 校准领域
CALIBRATION_SOURCE_KEYS: Tuple[str, ...] = (
    "parts",
    "part_operations",
    "external_groups",
    "op_types",
    "batches",
    "batch_operations",
    "batch_external_contexts",
    "workbench_entity_refs",
    "workbench_plan_identity",
    "workbench_template_lineage",
    "execution_ledger",
    "calibration_adoptions",
    "schedule_rows",
    "schedule_history",
)


def read_source_revisions(conn: sqlite3.Connection, keys: Iterable[str]) -> Dict[str, int]:
    requested = tuple(dict.fromkeys(str(key) for key in keys))
    if not requested:
        return {}
    by_key = select_source_revisions(conn, requested)
    if len(by_key) != len(requested):
        missing = sorted(set(requested) - set(by_key))
        raise RuntimeError("Missing workbench source revision keys: " + ", ".join(missing))
    return by_key
