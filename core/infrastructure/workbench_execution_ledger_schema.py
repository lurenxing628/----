"""Execution ledger DDL and structural contract checks."""

from core.infrastructure.workbench_metadata_schema import canonical_sql

from .schema_structure import schema_objects

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
            operation_ref TEXT NOT NULL, recorded_against_task_ref TEXT NOT NULL,
            recorded_against_plan_ref TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('manual', 'excel')),
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(recorded_against_task_ref) REFERENCES WorkbenchTaskRefs(ref),
            FOREIGN KEY(recorded_against_plan_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        )""",
        "WorkbenchProductionReportRevisions": f"""CREATE TABLE WorkbenchProductionReportRevisions (
            revision_ref {_REF.format('revision_ref')} PRIMARY KEY,
            report_ref TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0),
            previous_revision_ref TEXT, action TEXT NOT NULL CHECK(action IN ('create', 'supplement', 'correct')),
            values_json TEXT NOT NULL, reason TEXT NOT NULL,
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator)) > 0),
            declared_operator TEXT NOT NULL, recorded_at TEXT NOT NULL,
            request_key TEXT NOT NULL,
            UNIQUE(report_ref, sequence), UNIQUE(previous_revision_ref),
            FOREIGN KEY(report_ref) REFERENCES WorkbenchProductionReports(report_ref),
            FOREIGN KEY(previous_revision_ref) REFERENCES WorkbenchProductionReportRevisions(revision_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""",
        "idx_wb_execution_reports_operation": "CREATE INDEX idx_wb_execution_reports_operation ON WorkbenchProductionReports(operation_ref, recorded_at, report_ref)",
        "idx_wb_execution_reports_task": "CREATE INDEX idx_wb_execution_reports_task ON WorkbenchProductionReports(recorded_against_task_ref)",
        "idx_wb_execution_revisions_request": "CREATE INDEX idx_wb_execution_revisions_request ON WorkbenchProductionReportRevisions(request_key)",
        "idx_wb_execution_task_operation": "CREATE INDEX idx_wb_execution_task_operation ON WorkbenchPlanSourceRefs(operation_ref, kind, version)",
        "idx_wb_execution_source_row_history": "CREATE INDEX idx_wb_execution_source_row_history ON WorkbenchPlanSourceRefs(kind, source_key, version, operation_id)",
        "idx_wb_execution_resource_history": "CREATE INDEX idx_wb_execution_resource_history ON WorkbenchEntityRefs(kind, entity_key)",
    }
    for table, stem in (("WorkbenchProductionReports", "reports"),
                        ("WorkbenchProductionReportRevisions", "revisions")):
        for event in ("update", "delete"):
            name = "wb_execution_" + stem + "_no_" + event
            objects[name] = f"CREATE TRIGGER {name} BEFORE {event.upper()} ON {table} BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END"
        name = "wb_execution_" + stem + "_clock"
        objects[name] = f"CREATE TRIGGER {name} AFTER INSERT ON {table} BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END"
    return objects


def execution_ledger_contract_issues(conn, *, structure=None):
    """SELECT-only structural check. Missing/partial schemas are never repaired."""
    actual = schema_objects(conn, structure=structure)
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
