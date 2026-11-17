"""Execution ledger DDL and structural contract checks."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import (
    REPORT_REVISION_ACTION_VALUES,
    REPORT_SOURCE_VALUES,
    count_check,
    enum_check,
    flag_check,
    integer_sum_check,
    nullable_count_check,
    positive_count_check,
)

from .schema_structure import SchemaStructure

_REF = "TEXT NOT NULL CHECK(length({0}) = 48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def execution_ledger_objects():
    objects = {
        "WorkbenchExecutionLedgerClock": """CREATE TABLE WorkbenchExecutionLedgerClock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0),
            next_report_no INTEGER NOT NULL CHECK(typeof(next_report_no) = 'integer' AND next_report_no > 0)
        )""",
        "WorkbenchProductionReports": f"""CREATE TABLE WorkbenchProductionReports (
            report_ref {_REF.format('report_ref')} PRIMARY KEY,
            report_no TEXT NOT NULL UNIQUE CHECK(length(report_no) BETWEEN 1 AND 64),
            operation_ref TEXT NOT NULL,
            recorded_against_task_ref {_REF.format('recorded_against_task_ref')},
            recorded_against_plan_ref TEXT NOT NULL,
            source TEXT NOT NULL {enum_check('source', REPORT_SOURCE_VALUES)},
            recorded_at TEXT NOT NULL,
            current_revision_ref TEXT,
            revision_count INTEGER NOT NULL DEFAULT 1 {positive_count_check('revision_count')},
            voided INTEGER NOT NULL DEFAULT 0 {flag_check('voided')},
            actual_start TEXT,
            actual_end TEXT,
            completed_quantity INTEGER {nullable_count_check('completed_quantity')},
            effective_processing_hours TEXT,
            actual_machine_ref TEXT,
            actual_operator_ref TEXT,
            remark TEXT NOT NULL DEFAULT '',
            current_local_operator TEXT NOT NULL DEFAULT '',
            current_declared_operator TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(recorded_against_plan_ref) REFERENCES ScheduleHistory(plan_ref)
        )""",
        "WorkbenchProductionReportRevisions": f"""CREATE TABLE WorkbenchProductionReportRevisions (
            revision_ref {_REF.format('revision_ref')} PRIMARY KEY,
            report_ref TEXT NOT NULL, sequence INTEGER NOT NULL {positive_count_check('sequence')},
            previous_revision_ref TEXT, action TEXT NOT NULL {enum_check('action', REPORT_REVISION_ACTION_VALUES)},
            values_json TEXT NOT NULL, reason TEXT NOT NULL,
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator)) > 0),
            declared_operator TEXT NOT NULL, recorded_at TEXT NOT NULL,
            request_key TEXT NOT NULL,
            UNIQUE(report_ref, sequence), UNIQUE(previous_revision_ref),
            FOREIGN KEY(report_ref) REFERENCES WorkbenchProductionReports(report_ref),
            FOREIGN KEY(previous_revision_ref) REFERENCES WorkbenchProductionReportRevisions(revision_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""",
        "OperationExecutionStates": f"""CREATE TABLE OperationExecutionStates (
            operation_ref {_REF.format('operation_ref')} PRIMARY KEY,
            active_report_count INTEGER NOT NULL {count_check('active_report_count')},
            known_completed_quantity INTEGER NOT NULL {integer_sum_check('known_completed_quantity')},
            unknown_quantity_count INTEGER NOT NULL {count_check('unknown_quantity_count')},
            internal_complete_flag INTEGER NOT NULL {flag_check('internal_complete_flag')},
            external_complete_flag INTEGER NOT NULL {flag_check('external_complete_flag')},
            any_actual_end INTEGER NOT NULL {flag_check('any_actual_end')},
            first_actual_start TEXT,
            max_actual_end TEXT,
            known_effective_hours_text TEXT,
            unknown_hour_count INTEGER NOT NULL {count_check('unknown_hour_count')},
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        )""",
        "idx_wb_execution_reports_operation": "CREATE INDEX idx_wb_execution_reports_operation ON WorkbenchProductionReports(operation_ref, recorded_at, report_ref)",
        "idx_wb_execution_reports_task": "CREATE INDEX idx_wb_execution_reports_task ON WorkbenchProductionReports(recorded_against_task_ref)",
        "idx_wb_exec_reports_active_op": "CREATE INDEX idx_wb_exec_reports_active_op ON WorkbenchProductionReports(operation_ref, recorded_at, report_no) WHERE voided = 0",
        "idx_wb_exec_reports_active_machine": "CREATE INDEX idx_wb_exec_reports_active_machine ON WorkbenchProductionReports(actual_machine_ref, operation_ref) WHERE voided = 0 AND actual_machine_ref IS NOT NULL",
        "idx_wb_exec_reports_active_operator": "CREATE INDEX idx_wb_exec_reports_active_operator ON WorkbenchProductionReports(actual_operator_ref, operation_ref) WHERE voided = 0 AND actual_operator_ref IS NOT NULL",
        "idx_wb_execution_revisions_request": "CREATE INDEX idx_wb_execution_revisions_request ON WorkbenchProductionReportRevisions(request_key)",
        "idx_wb_execution_resource_history": "CREATE INDEX idx_wb_execution_resource_history ON WorkbenchEntityRefs(kind, entity_key)",
        "wb_execution_reports_identity_immutable": """CREATE TRIGGER wb_execution_reports_identity_immutable BEFORE UPDATE ON WorkbenchProductionReports
            WHEN NEW.report_ref IS NOT OLD.report_ref
              OR NEW.report_no IS NOT OLD.report_no
              OR NEW.operation_ref IS NOT OLD.operation_ref
              OR NEW.recorded_against_task_ref IS NOT OLD.recorded_against_task_ref
              OR NEW.recorded_against_plan_ref IS NOT OLD.recorded_against_plan_ref
              OR NEW.source IS NOT OLD.source
              OR NEW.recorded_at IS NOT OLD.recorded_at
            BEGIN SELECT RAISE(ABORT, 'execution report identity is immutable'); END""",
        "wb_execution_reports_no_delete": "CREATE TRIGGER wb_execution_reports_no_delete BEFORE DELETE ON WorkbenchProductionReports BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END",
        "wb_execution_reports_clock": "CREATE TRIGGER wb_execution_reports_clock AFTER INSERT ON WorkbenchProductionReports BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END",
    }
    for event in ("update", "delete"):
        name = "wb_execution_revisions_no_" + event
        objects[name] = f"CREATE TRIGGER {name} BEFORE {event.upper()} ON WorkbenchProductionReportRevisions BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END"
    objects["wb_execution_revisions_clock"] = "CREATE TRIGGER wb_execution_revisions_clock AFTER INSERT ON WorkbenchProductionReportRevisions BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END"
    return objects


def execution_ledger_contract_issues(conn, *, structure: SchemaStructure):
    """SELECT-only structural check. Missing/partial schemas are never repaired."""
    actual = structure.sql
    issues = []
    declared = execution_ledger_objects()
    for name, sql in declared.items():
        if name not in actual:
            issues.append("missing_execution_ledger:" + name)
        elif canonical_sql(sql) != canonical_sql(actual[name]):
            issues.append("invalid_execution_ledger:" + name)
    if not issues:
        rows = conn.execute("SELECT singleton, revision, next_report_no FROM WorkbenchExecutionLedgerClock LIMIT 2").fetchall()
        if len(rows) != 1 or rows[0][0] != 1 or any(type(x) is not int or x < 1 for x in rows[0][1:]):
            issues.append("invalid_execution_ledger:clock")
    return issues


_INITIALIZATION_EMPTY_CHECKS = (
    "NOT EXISTS (SELECT 1 FROM WorkbenchProductionReports LIMIT 1)",
    "NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions LIMIT 1)",
    "NOT EXISTS (SELECT 1 FROM OperationExecutionStates LIMIT 1)",
    "NOT EXISTS (SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1)",
)


def execution_ledger_initialization_sql() -> str:
    """Seed for the end of a NEW database's DDL script (schema.sql), never a repair script.

    A brand-new database gets clock revision 1 and report number 1; when any ledger source already
    exists the revision CHECK deliberately aborts the initialization instead of guessing a state.
    """
    return ("INSERT INTO WorkbenchExecutionLedgerClock(singleton, revision, next_report_no) "
            "SELECT 1, CASE WHEN " + " AND ".join(_INITIALIZATION_EMPTY_CHECKS) + " THEN 1 ELSE 0 END, 1 "
            "WHERE NOT EXISTS (SELECT 1 FROM WorkbenchExecutionLedgerClock);")
