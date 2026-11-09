"""Unified source revision table and triggers for workbench snapshot bindings."""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql

SOURCE_REVISIONS_TABLE = "WorkbenchSourceRevisions"

_ORDINARY_SOURCE_TABLES: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # 基础与主数据
    ("parts", "Parts", ("part_no", "part_name", "route_raw", "route_parsed", "remark", "created_at", "updated_at")),
    ("part_operations", "PartOperations", ("id", "part_no", "seq", "op_type_id", "op_type_name", "source",
        "supplier_id", "ext_days", "ext_group_id", "setup_hours", "unit_hours", "status", "created_at")),
    ("external_groups", "ExternalGroups", ("group_id", "part_no", "start_seq", "end_seq", "merge_mode", "total_days",
        "supplier_id", "remark", "created_at")),
    ("op_types", "OpTypes", ("op_type_id", "name", "category", "default_hours", "remark", "created_at")),
    ("machines", "Machines", ("machine_id", "name", "op_type_id", "category", "status", "remark", "created_at",
        "updated_at", "team_id")),
    ("machine_op_types", "MachineOpTypes", ("machine_id", "op_type_id")),
    ("machine_downtimes", "MachineDowntimes", ("id", "machine_id", "scope_type", "scope_value", "start_time",
        "end_time", "reason_code", "reason_detail", "status", "created_at", "updated_at")),
    ("operators", "Operators", ("operator_id", "name", "status", "remark", "created_at", "updated_at", "team_id")),
    ("operator_skills", "OperatorSkill", ("id", "operator_id", "op_type_id", "skill_level", "is_primary",
        "created_at")),
    ("operator_machines", "OperatorMachine", ("id", "operator_id", "machine_id", "skill_level", "is_primary",
        "created_at")),
    ("materials", "Materials", ("material_id", "name", "spec", "unit", "stock_qty", "status", "remark", "created_at")),
    ("suppliers", "Suppliers", ("supplier_id", "name", "default_days", "status", "remark", "created_at")),
    ("work_calendar", "WorkCalendar", ("date", "day_type", "efficiency", "allow_normal", "allow_urgent", "remark",
        "periods_json")),
    ("operator_calendar", "OperatorCalendar", ("operator_id", "date", "day_type", "efficiency", "allow_normal",
        "allow_urgent", "remark", "periods_json")),
    ("resource_teams", "ResourceTeams", ("team_id", "name", "status", "remark", "created_at", "updated_at")),
    # 工作台扩展主数据
    ("workbench_operator_profiles", "WorkbenchOperatorProfiles", ("operator_id", "shift_profile_id", "skills_declared",
        "inactive_reason")),
    ("workbench_supplier_op_types", "WorkbenchSupplierOpTypes", ("supplier_id", "op_type_id")),
    ("workbench_supplier_profiles", "WorkbenchSupplierProfiles", ("supplier_id", "inactive_reason")),
    ("workbench_machine_groups", "WorkbenchMachineGroups", ("group_id", "name", "status", "remark", "created_at")),
    ("workbench_machine_group_members", "WorkbenchMachineGroupMembers", ("machine_id", "group_id")),
    ("workbench_shift_profiles", "WorkbenchShiftProfiles", ("profile_id", "name", "anchor_date", "cycle_days", "status",
        "remark", "created_at")),
    ("workbench_shift_pattern_days", "WorkbenchShiftPatternDays", ("profile_id", "day_offset", "is_rest",
        "periods_json")),
    ("workbench_calendar_defaults", "WorkbenchCalendarDefaults", ("singleton", "state_ref", "revision",
        "periods_json")),
    ("workbench_op_type_policies", "WorkbenchOpTypePolicies", ("op_type_id", "default_merge_mode")),
    ("workbench_entity_refs", "WorkbenchEntityRefs", ("ref", "kind", "entity_key", "alternate_key", "revision",
        "active", "created_at_utc")),
    # 批次与工艺确认
    ("batches", "Batches", ("batch_id", "part_no", "part_name", "quantity", "due_date", "priority", "ready_status",
        "ready_date", "status", "remark", "created_at", "updated_at")),
    ("batch_operations", "BatchOperations", ("id", "op_code", "batch_id", "piece_id", "seq", "op_type_id",
        "op_type_name", "source", "machine_id", "operator_id", "supplier_id", "setup_hours", "unit_hours", "ext_days",
        "status", "created_at")),
    ("batch_external_contexts", "BatchExternalContexts", ("operation_id", "part_no", "sequence",
        "template_operation_id", "template_status", "group_id", "group_part_no", "start_sequence", "end_sequence",
        "merge_mode", "total_days", "supplier_id", "group_ref", "template_operation_ref", "origin", "captured_at")),
    ("batch_materials", "BatchMaterials", ("id", "batch_id", "material_id", "required_qty", "available_qty",
        "ready_status")),
    ("batch_material_reviews", "BatchMaterialReviews", ("requirement_id", "batch_quantity")),
    ("batch_material_stages", "BatchMaterialStages", ("requirement_id", "operation_id")),
    ("batch_material_arrivals", "BatchMaterialArrivals", ("id", "requirement_id", "arrival_date", "quantity")),
    ("batch_quantity_splits", "BatchQuantitySplits", ("id", "source_batch_id", "child_batch_id", "original_quantity",
        "split_quantity", "allocation_date", "created_at")),
    ("workbench_process_workflow", "WorkbenchProcessWorkflow", ("part_ref", "route_confirmed_at", "route_confirmed_by",
        "route_content_json", "source_confirmed_at", "source_confirmed_by", "source_content_json", "hours_confirmed_at",
        "hours_confirmed_by", "hours_content_json")),
    ("workbench_process_operation_confirmations", "WorkbenchProcessOperationConfirmations", ("part_ref",
        "operation_ref", "stage", "confirmed_at", "confirmed_by", "content_json")),
    ("workbench_template_lineage", "WorkbenchTemplateLineageOrigins", ("lineage_ref", "operation_ref",
        "template_operation_ref", "template_revision", "source_operation_ref", "source_lineage_ref", "source_event_id",
        "source_eligible", "birth_event_id", "evidence_version", "template_snapshot", "instance_snapshot",
        "recorded_at_utc")),
    ("workbench_template_lineage", "WorkbenchTemplateLineageEvents", ("event_id", "operation_ref", "event_type",
        "affects_calibration", "reason", "recorded_at_utc", "id", "op_code", "batch_id", "piece_id", "seq",
        "op_type_id", "op_type_name", "source", "machine_id", "operator_id", "supplier_id", "setup_hours", "unit_hours",
        "ext_days", "status", "created_at", "batch_ref", "part_ref", "quantity")),
    # 计划与配置
    ("schedule_history", "ScheduleHistory", ("id", "schedule_time", "version", "strategy", "batch_count", "op_count",
        "result_status", "result_summary", "created_by")),
    ("schedule_version_seq", "ScheduleVersionSeq", ("version",)),
    ("schedule_config", "ScheduleConfig", ("id", "config_key", "config_value", "description", "updated_at")),
    ("workbench_plan_identity", "WorkbenchPlanSourceRefs", ("ref", "kind", "source_key", "alternate_key", "extra_key",
        "version", "plan_role", "source_table", "owner_key", "operation_id", "operation_ref", "active")),
    ("workbench_plan_identity", "WorkbenchTaskRefs", ("ref", "plan_ref", "row_ref")),
    ("workbench_plan_identity", "WorkbenchPlanIdentityClock", ("singleton", "revision")),
    # 执行、外协、看板、校准、运行、试调
    ("execution_ledger", "WorkbenchExecutionLedgerClock", ("singleton", "revision", "next_report_no")),
    ("execution_ledger", "WorkbenchProductionReports", ("report_ref", "report_no", "operation_ref",
        "recorded_against_task_ref", "recorded_against_plan_ref", "source", "recorded_at")),
    ("execution_ledger", "WorkbenchProductionReportRevisions", ("revision_ref", "report_ref", "sequence",
        "previous_revision_ref", "action", "values_json", "reason", "local_operator", "declared_operator",
        "recorded_at", "request_key")),
    ("execution_ledger", "WorkbenchProductionReportVoids", ("void_fact_ref", "report_ref", "original_revision_ref",
        "reason", "local_operator", "declared_operator", "recorded_at", "request_key")),
    ("outsourcing", "WorkbenchOutsourcingOperationOrigins", ("operation_ref", "batch_ref")),
    ("outsourcing", "WorkbenchOutsourcingSourceConfirmations", ("operation_ref", "batch_ref", "fact_ref")),
    ("outsourcing", "WorkbenchOutsourcingMembers", ("operation_ref", "outsourcing_ref")),
    ("outsourcing", "WorkbenchOutsourcingReceipts", ("outsourcing_ref", "target_kind", "batch_ref", "supplier_ref",
        "origin_json", "identity_json", "created_at")),
    ("outsourcing", "WorkbenchOutsourcingFacts", ("fact_ref", "outsourcing_ref", "sequence", "previous_fact_ref",
        "sent", "planned", "returned", "confirmed_state", "declared_operator", "local_operator", "reason",
        "recorded_at", "before_json", "source_facts_json", "request_key")),
    ("dashboard_items", "WorkbenchDashboardItems", ("item_ref", "category", "batch_ref", "task_ref")),
    ("dashboard_items", "WorkbenchDashboardDowntimeRefs", ("ref", "source_id", "active", "revision")),
    ("dashboard_items", "WorkbenchDashboardExternalItems", ("item_ref", "category", "outsourcing_ref")),
    ("dashboard_handling", "WorkbenchDashboardStates", ("item_ref", "revision", "handling_json", "origin_json",
        "updated_at")),
    ("dashboard_handling", "WorkbenchDashboardHistory", ("history_ref", "item_ref", "sequence", "action", "before_json",
        "after_json", "source_json", "source_facts_json", "reason", "local_operator", "recorded_at", "request_key")),
    ("dashboard_handling", "WorkbenchDashboardExternalStates", ("item_ref", "revision", "handling_json", "origin_json",
        "updated_at")),
    ("dashboard_handling", "WorkbenchDashboardExternalHistory", ("history_ref", "item_ref", "sequence", "action",
        "before_json", "after_json", "source_json", "source_facts_json", "reason", "local_operator", "recorded_at",
        "request_key")),
    ("calibration_adoptions", "WorkbenchCalibrationAdoptions", ("adoption_ref", "template_operation_ref", "request_key",
        "template_revision_before", "template_revision_after", "old_unit_hours", "new_unit_hours", "reason",
        "declared_operator", "confirmed", "application_operator", "adopted_at", "generated_at", "method_version",
        "sample_count", "evidence_json", "template_before", "template_after")),
    ("run_jobs", "WorkbenchRunJobs", ("run_ref", "request_key", "input_ref", "normalized_input_json", "facts_json",
        "execution_json", "baseline_json", "accepted_at", "state", "stage", "executor_ref", "started_at", "finished_at",
        "error_json")),
    ("run_jobs", "WorkbenchRunReceipts", ("receipt_ref", "run_ref", "state", "result_json", "recorded_at")),
    ("run_jobs", "WorkbenchRunCandidates", ("candidate_ref", "run_ref", "candidate_key", "sequence", "status",
        "task_count", "artifact_json")),
    ("run_jobs", "WorkbenchRunCandidateTasks", ("row_ref", "candidate_ref", "operation_ref", "ordinal",
        "payload_json")),
    ("run_jobs", "WorkbenchRunAdmissionReadModels", ("run_ref", "projection_version", "scope_json", "decision_json")),
    ("run_jobs", "WorkbenchRunDecisionReadModels", ("run_ref", "projection_version", "header_json", "context_json",
        "memberships_json", "calendar_json", "official_json", "process_json")),
    ("run_jobs", "WorkbenchRunCandidateReadModels", ("candidate_ref", "run_ref", "projection_version", "summary_json",
        "preparation_json", "completion_json", "delivery_json", "delivery_detail_json", "arrangements_json")),
    ("trial_records", "WorkbenchTrialDrafts", ("draft_ref", "base_kind", "base_ref", "admission_json", "row_count",
        "revision", "status", "validation_json", "created_at", "updated_at", "local_operator", "request_key")),
    ("trial_records", "WorkbenchTrialRows", ("row_ref", "task_ref", "draft_ref", "operation_ref", "source_task_ref",
        "source_row_ref", "ordinal", "original_json", "current_json")),
    ("trial_records", "WorkbenchTrialChanges", ("change_ref", "draft_ref", "task_ref", "revision", "before_json",
        "after_json", "validation_json", "recorded_at", "local_operator", "request_key")),
    ("trial_records", "WorkbenchTrialScenarios", ("scenario_ref", "draft_ref", "name", "revision", "snapshot_json",
        "saved_at", "local_operator", "request_key")),
    ("trial_records", "WorkbenchTrialScenarioRows", ("row_ref", "task_ref", "scenario_ref", "source_row_ref",
        "payload_json")),
)

_SCHEDULE_COLUMNS = ("id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version", "created_at")
_SYSTEM_CONFIG_COLUMNS = ("id", "config_key", "config_value", "description", "updated_at")
_COMMAND_RECEIPT_COLUMNS = ("request_key", "receipt_ref", "action", "context_ref", "outcome_json", "input_json", "committed_at_utc")
_ENTITY_REF_COLUMNS = ("ref", "kind", "entity_key", "alternate_key", "revision", "active", "created_at_utc")

SOURCE_REVISION_KEYS: Tuple[str, ...] = tuple(
    dict.fromkeys(
        [source_key for source_key, _table, _cols in _ORDINARY_SOURCE_TABLES]
        + [
            "schedule_rows",
            "schedule_references",
            "scheduling_preferences",
            "system_config",
            "trial_adoption_receipts",
            "production_input_receipts",
        ]
    )
)


def _changed_predicate(columns: Tuple[str, ...]) -> str:
    return " OR ".join(f'OLD."{col}" IS NOT NEW."{col}"' for col in columns)


def _bump_sql(source_key: str) -> str:
    return f"UPDATE WorkbenchSourceRevisions SET revision = revision + 1 WHERE source_key = '{source_key}';"


def _ordinary_triggers(source_key: str, table: str, columns: Tuple[str, ...]) -> Dict[str, str]:
    stem = "wb_src_rev_" + table.lower()
    bump = _bump_sql(source_key)
    changed = _changed_predicate(columns)
    insert_when = ""
    if table == "WorkbenchPlanIdentityClock":
        insert_when = ' WHEN NEW."singleton" IS NOT 1 OR NEW."revision" IS NOT 1'
    elif table == "WorkbenchExecutionLedgerClock":
        insert_when = ' WHEN NEW."singleton" IS NOT 1 OR NEW."revision" IS NOT 1 OR NEW."next_report_no" IS NOT 1'
    return {
        stem + "_insert": f'CREATE TRIGGER {stem}_insert AFTER INSERT ON "{table}"{insert_when} BEGIN {bump} END',
        stem + "_update": f'CREATE TRIGGER {stem}_update AFTER UPDATE ON "{table}" WHEN {changed} BEGIN {bump} END',
        stem + "_delete": f'CREATE TRIGGER {stem}_delete AFTER DELETE ON "{table}" BEGIN {bump} END',
    }


def _schedule_triggers() -> Dict[str, str]:
    bump_rows = _bump_sql("schedule_rows")
    bump_refs = _bump_sql("schedule_references")
    changed_all = _changed_predicate(_SCHEDULE_COLUMNS)
    changed_refs = 'OLD."op_id" IS NOT NEW."op_id" OR OLD."version" IS NOT NEW."version"'
    return {
        "wb_src_rev_schedule_rows_insert": f'CREATE TRIGGER wb_src_rev_schedule_rows_insert AFTER INSERT ON "Schedule" BEGIN {bump_rows} END',
        "wb_src_rev_schedule_rows_update": f'CREATE TRIGGER wb_src_rev_schedule_rows_update AFTER UPDATE ON "Schedule" WHEN {changed_all} BEGIN {bump_rows} END',
        "wb_src_rev_schedule_rows_delete": f'CREATE TRIGGER wb_src_rev_schedule_rows_delete AFTER DELETE ON "Schedule" BEGIN {bump_rows} END',
        "wb_src_rev_schedule_references_insert": f'CREATE TRIGGER wb_src_rev_schedule_references_insert AFTER INSERT ON "Schedule" BEGIN {bump_refs} END',
        "wb_src_rev_schedule_references_update": f'CREATE TRIGGER wb_src_rev_schedule_references_update AFTER UPDATE ON "Schedule" WHEN {changed_refs} BEGIN {bump_refs} END',
        "wb_src_rev_schedule_references_delete": f'CREATE TRIGGER wb_src_rev_schedule_references_delete AFTER DELETE ON "Schedule" BEGIN {bump_refs} END',
    }


def _system_config_triggers() -> Dict[str, str]:
    pref_key = f"'{SCHEDULING_PREFERENCES_KEY}'"
    bump_pref = _bump_sql("scheduling_preferences")
    bump_sys = _bump_sql("system_config")
    changed = _changed_predicate(_SYSTEM_CONFIG_COLUMNS)
    return {
        "wb_src_rev_scheduling_preferences_insert": (
            f'CREATE TRIGGER wb_src_rev_scheduling_preferences_insert AFTER INSERT ON "SystemConfig" '
            f'WHEN NEW."config_key" = {pref_key} BEGIN {bump_pref} END'
        ),
        "wb_src_rev_scheduling_preferences_update": (
            f'CREATE TRIGGER wb_src_rev_scheduling_preferences_update AFTER UPDATE ON "SystemConfig" '
            f'WHEN (OLD."config_key" = {pref_key} OR NEW."config_key" = {pref_key}) AND ({changed}) BEGIN {bump_pref} END'
        ),
        "wb_src_rev_scheduling_preferences_delete": (
            f'CREATE TRIGGER wb_src_rev_scheduling_preferences_delete AFTER DELETE ON "SystemConfig" '
            f'WHEN OLD."config_key" = {pref_key} BEGIN {bump_pref} END'
        ),
        "wb_src_rev_system_config_insert": (
            f'CREATE TRIGGER wb_src_rev_system_config_insert AFTER INSERT ON "SystemConfig" '
            f'WHEN NEW."config_key" != {pref_key} BEGIN {bump_sys} END'
        ),
        "wb_src_rev_system_config_update": (
            f'CREATE TRIGGER wb_src_rev_system_config_update AFTER UPDATE ON "SystemConfig" '
            f'WHEN (OLD."config_key" != {pref_key} OR NEW."config_key" != {pref_key}) AND ({changed}) BEGIN {bump_sys} END'
        ),
        "wb_src_rev_system_config_delete": (
            f'CREATE TRIGGER wb_src_rev_system_config_delete AFTER DELETE ON "SystemConfig" '
            f'WHEN OLD."config_key" != {pref_key} BEGIN {bump_sys} END'
        ),
    }


def _command_receipts_triggers() -> Dict[str, str]:
    bump_adopt = _bump_sql("trial_adoption_receipts")
    bump_prod = _bump_sql("production_input_receipts")
    changed = _changed_predicate(_COMMAND_RECEIPT_COLUMNS)
    adopt_new = (
        'NEW."action" = \'trial.scenario.adopt\' '
        'AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = \'trial_adoption\''
    )
    adopt_old = (
        'OLD."action" = \'trial.scenario.adopt\' '
        'AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = \'trial_adoption\''
    )
    prod_new = (
        'NEW."action" IS NOT \'trial.scenario.adopt\' '
        'AND aps_receipt_revision_category(NEW."action", NEW."outcome_json") = \'production_input\''
    )
    prod_old = (
        'OLD."action" IS NOT \'trial.scenario.adopt\' '
        'AND aps_receipt_revision_category(OLD."action", OLD."outcome_json") = \'production_input\''
    )
    return {
        "wb_src_rev_trial_adoption_receipts_insert": (
            f'CREATE TRIGGER wb_src_rev_trial_adoption_receipts_insert AFTER INSERT ON "WorkbenchCommandReceipts" '
            f"WHEN {adopt_new} BEGIN {bump_adopt} END"
        ),
        "wb_src_rev_trial_adoption_receipts_update": (
            f'CREATE TRIGGER wb_src_rev_trial_adoption_receipts_update AFTER UPDATE ON "WorkbenchCommandReceipts" '
            f"WHEN ({adopt_old} OR {adopt_new}) AND ({changed}) BEGIN {bump_adopt} END"
        ),
        "wb_src_rev_trial_adoption_receipts_delete": (
            f'CREATE TRIGGER wb_src_rev_trial_adoption_receipts_delete AFTER DELETE ON "WorkbenchCommandReceipts" '
            f"WHEN {adopt_old} BEGIN {bump_adopt} END"
        ),
        "wb_src_rev_production_input_receipts_insert": (
            f'CREATE TRIGGER wb_src_rev_production_input_receipts_insert AFTER INSERT ON "WorkbenchCommandReceipts" '
            f"WHEN {prod_new} BEGIN {bump_prod} END"
        ),
        "wb_src_rev_production_input_receipts_update": (
            f'CREATE TRIGGER wb_src_rev_production_input_receipts_update AFTER UPDATE ON "WorkbenchCommandReceipts" '
            f"WHEN ({prod_old} OR {prod_new}) AND ({changed}) BEGIN {bump_prod} END"
        ),
        "wb_src_rev_production_input_receipts_delete": (
            f'CREATE TRIGGER wb_src_rev_production_input_receipts_delete AFTER DELETE ON "WorkbenchCommandReceipts" '
            f"WHEN {prod_old} BEGIN {bump_prod} END"
        ),
    }


def _entity_refs_shared_triggers() -> Dict[str, str]:
    changed = _changed_predicate(_ENTITY_REF_COLUMNS)
    triggers: Dict[str, str] = {}
    for kind, source_key in (("op_type", "op_types"), ("supplier", "suppliers")):
        stem = f"wb_src_rev_entity_refs_{source_key}"
        bump = _bump_sql(source_key)
        triggers[stem + "_insert"] = (
            f'CREATE TRIGGER {stem}_insert AFTER INSERT ON "WorkbenchEntityRefs" '
            f'WHEN NEW."kind" = \'{kind}\' BEGIN {bump} END'
        )
        triggers[stem + "_update"] = (
            f'CREATE TRIGGER {stem}_update AFTER UPDATE ON "WorkbenchEntityRefs" '
            f'WHEN (OLD."kind" = \'{kind}\' OR NEW."kind" = \'{kind}\') AND ({changed}) BEGIN {bump} END'
        )
        triggers[stem + "_delete"] = (
            f'CREATE TRIGGER {stem}_delete AFTER DELETE ON "WorkbenchEntityRefs" '
            f'WHEN OLD."kind" = \'{kind}\' BEGIN {bump} END'
        )
    return triggers


def source_revisions_objects() -> Dict[str, str]:
    objects: Dict[str, str] = {
        SOURCE_REVISIONS_TABLE: """CREATE TABLE WorkbenchSourceRevisions (
        source_key TEXT PRIMARY KEY NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision) = 'integer' AND revision >= 1)
    )""",
    }
    for source_key, table, columns in _ORDINARY_SOURCE_TABLES:
        objects.update(_ordinary_triggers(source_key, table, columns))
    objects.update(_entity_refs_shared_triggers())
    objects.update(_schedule_triggers())
    objects.update(_system_config_triggers())
    objects.update(_command_receipts_triggers())
    return objects


def source_revisions_initialization_sql() -> str:
    values = ", ".join(f"('{key}', 1)" for key in SOURCE_REVISION_KEYS)
    return (
        "INSERT INTO WorkbenchSourceRevisions(source_key, revision) VALUES "
        + values
        + " ON CONFLICT(source_key) DO NOTHING;"
    )



def select_source_revisions(conn, keys: Tuple[str, ...]) -> Dict[str, int]:
    """Stored revisions of these distinct source keys; keys without a row are absent from the result."""
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(
        "SELECT source_key, revision FROM WorkbenchSourceRevisions WHERE source_key IN (" + placeholders + ") "
        "ORDER BY source_key",
        keys,
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def source_revisions_contract_issues(conn, *, structure: SchemaStructure) -> List[str]:
    actual = structure.sql
    issues: List[str] = []
    for name, sql in source_revisions_objects().items():
        if name not in actual:
            issues.append("missing_workbench_source_revisions: " + name)
        elif canonical_sql(actual[name]) != canonical_sql(sql):
            issues.append("bad_workbench_source_revisions: " + name)
    if not issues:
        rows = conn.execute(
            "SELECT source_key, revision FROM WorkbenchSourceRevisions ORDER BY source_key"
        ).fetchall()
        by_key = {row[0]: row[1] for row in rows}
        if any(key not in by_key for key in SOURCE_REVISION_KEYS):
            issues.append("missing_workbench_source_revisions_seed")
        elif any(type(by_key[key]) is not int or by_key[key] < 1 for key in SOURCE_REVISION_KEYS):
            issues.append("bad_workbench_source_revisions_seed")
    return issues
