"""Explicit, caller-transactional ledger installation. Never called by a query."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql

LEGACY_COLUMNS = (
    "id", "schedule_version", "schedule_id", "op_id", "batch_id", "source_table",
    "effective_plan_role", "scenario_id", "event_type", "reported_status", "event_time",
    "actual_machine_id", "actual_operator_id", "quantity_done", "quantity_scrapped",
    "reason_code", "reason_detail", "severity", "impact_minutes", "affected_machine_id",
    "affected_operator_id", "handling_status", "suggest_reschedule", "remark", "created_by",
    "idempotency_key", "request_fingerprint", "previous_state_revision", "created_at",
)
_REF = "TEXT NOT NULL CHECK(length({0}) = 48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def _capture_sql(where):
    # A source-row tombstone is evidence, a same-number replacement is not.
    columns = ", ".join(LEGACY_COLUMNS)
    values = ", ".join("e." + name for name in LEGACY_COLUMNS)
    return f"""INSERT INTO WorkbenchExecutionLegacyFacts
        (legacy_fact_ref, operation_ref, recorded_against_task_ref, recorded_against_plan_ref,
         actual_machine_ref, actual_operator_ref, {columns})
        SELECT lower(hex(randomblob(24))), r.operation_ref, t.ref, t.plan_ref,
            (SELECT CASE WHEN count(*)=1 THEN min(ref) END FROM WorkbenchEntityRefs
                WHERE kind='machine' AND entity_key=e.actual_machine_id),
            (SELECT CASE WHEN count(*)=1 THEN min(ref) END FROM WorkbenchEntityRefs
                WHERE kind='operator' AND entity_key=e.actual_operator_id), {values}
        FROM OperationExecutionEvents e
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.ref = (
            SELECT min(x.ref) FROM WorkbenchPlanSourceRefs x WHERE x.kind = 'schedule_row'
            AND x.source_table = 'schedule' AND e.source_table = 'schedule'
            AND e.effective_plan_role = 'adopted' AND e.scenario_id IS NULL
            AND x.source_key = CAST(e.schedule_id AS TEXT) AND x.version = e.schedule_version
            AND x.operation_id = e.op_id
            AND EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs owner JOIN BatchOperations bo
                ON bo.id = CAST(owner.source_key AS INTEGER) AND CAST(bo.id AS TEXT) = owner.source_key
                WHERE owner.ref = x.operation_ref AND owner.kind = 'operation' AND owner.active = 1
                AND bo.batch_id = e.batch_id)
            GROUP BY x.kind, x.source_key, x.version, x.operation_id HAVING count(*) = 1)
        LEFT JOIN WorkbenchPlanSourceRefs p ON p.kind = 'official' AND p.active = 1
            AND p.version = e.schedule_version
        LEFT JOIN WorkbenchTaskRefs t ON t.row_ref = r.ref AND t.plan_ref = p.ref
        WHERE {where};"""


def execution_ledger_objects():
    # No affinity: retain the original SQLite storage types, including damaged metadata.
    raw = ",\n".join(LEGACY_COLUMNS)
    objects = {
        "WorkbenchExecutionLedgerClock": """CREATE TABLE WorkbenchExecutionLedgerClock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0),
            next_report_no INTEGER NOT NULL CHECK(typeof(next_report_no) = 'integer' AND next_report_no > 0)
        )""",
        "WorkbenchExecutionLegacyFacts": f"""CREATE TABLE WorkbenchExecutionLegacyFacts (
            legacy_fact_ref {_REF.format('legacy_fact_ref')} PRIMARY KEY,
            operation_ref TEXT, recorded_against_task_ref TEXT, recorded_against_plan_ref TEXT,
            actual_machine_ref TEXT, actual_operator_ref TEXT,
            {raw}, UNIQUE(id)
        )""",
        "WorkbenchProductionReports": f"""CREATE TABLE WorkbenchProductionReports (
            report_ref {_REF.format('report_ref')} PRIMARY KEY,
            report_no TEXT NOT NULL UNIQUE CHECK(length(report_no) BETWEEN 1 AND 64),
            operation_ref TEXT NOT NULL, recorded_against_task_ref TEXT NOT NULL,
            recorded_against_plan_ref TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('manual', 'excel')),
            legacy_fact_ref TEXT UNIQUE, recorded_at TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(recorded_against_task_ref) REFERENCES WorkbenchTaskRefs(ref),
            FOREIGN KEY(recorded_against_plan_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
            FOREIGN KEY(legacy_fact_ref) REFERENCES WorkbenchExecutionLegacyFacts(legacy_fact_ref)
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
        "idx_wb_execution_legacy_operation": "CREATE INDEX idx_wb_execution_legacy_operation ON WorkbenchExecutionLegacyFacts(operation_ref, id)",
        "idx_wb_execution_legacy_unbound": "CREATE INDEX idx_wb_execution_legacy_unbound ON WorkbenchExecutionLegacyFacts(op_id) WHERE operation_ref IS NULL OR recorded_against_task_ref IS NULL",
        "idx_wb_execution_revisions_request": "CREATE INDEX idx_wb_execution_revisions_request ON WorkbenchProductionReportRevisions(request_key)",
        "idx_wb_execution_task_operation": "CREATE INDEX idx_wb_execution_task_operation ON WorkbenchPlanSourceRefs(operation_ref, kind, version)",
        "idx_wb_execution_source_row_history": "CREATE INDEX idx_wb_execution_source_row_history ON WorkbenchPlanSourceRefs(kind, source_key, version, operation_id)",
        "idx_wb_execution_resource_history": "CREATE INDEX idx_wb_execution_resource_history ON WorkbenchEntityRefs(kind, entity_key)",
    }
    for table, stem in (("WorkbenchProductionReports", "reports"),
                        ("WorkbenchProductionReportRevisions", "revisions"),
                        ("WorkbenchExecutionLegacyFacts", "legacy")):
        for event in ("update", "delete"):
            name = "wb_execution_" + stem + "_no_" + event
            objects[name] = f"CREATE TRIGGER {name} BEFORE {event.upper()} ON {table} BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END"
        name = "wb_execution_" + stem + "_clock"
        objects[name] = f"CREATE TRIGGER {name} AFTER INSERT ON {table} BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision = revision + 1 WHERE singleton = 1; END"
    objects["wb_execution_capture_legacy"] = ("CREATE TRIGGER wb_execution_capture_legacy AFTER INSERT ON OperationExecutionEvents BEGIN " +
                                               _capture_sql("e.id = NEW.id") + " END")
    return objects


def execution_ledger_contract_issues(conn):
    """SELECT-only structural check. Missing/partial schemas are never repaired."""
    actual = {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")}
    issues = []
    for name, sql in execution_ledger_objects().items():
        if name not in actual:
            issues.append("missing_execution_ledger:" + name)
        elif _canonical_sql(sql) != _canonical_sql(actual[name] or ""):
            issues.append("invalid_execution_ledger:" + name)
    if not issues:
        rows = conn.execute("SELECT singleton, revision, next_report_no FROM WorkbenchExecutionLedgerClock LIMIT 2").fetchall()
        if len(rows) != 1 or rows[0][0] != 1 or any(type(x) is not int or x < 1 for x in rows[0][1:]):
            issues.append("invalid_execution_ledger:clock")
    return issues


def install_execution_ledger(conn):
    """Install once inside an explicit migration transaction, without committing.

    Requires installed workbench metadata and permanent plan identities. Legacy
    rows with ambiguous identity are preserved with null bindings, not guessed.
    A partial/lost ledger is a restore problem, not permission to recreate refs.
    """
    if not conn.in_transaction:
        raise RuntimeError("install_execution_ledger requires the caller's migration transaction.")
    objects = execution_ledger_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects):
        issues = execution_ledger_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial execution ledger: " + "; ".join(issues))
        if conn.execute("SELECT 1 FROM OperationExecutionEvents e LEFT JOIN WorkbenchExecutionLegacyFacts f ON f.id=e.id WHERE f.id IS NULL LIMIT 1").fetchone():
            raise RuntimeError("Legacy execution identities are missing; restore a complete backup.")
        return
    required = {"WorkbenchPlanSourceRefs", "WorkbenchTaskRefs", "WorkbenchCommandReceipts", "WorkbenchEntityRefs"}
    if not required <= names:
        raise RuntimeError("Execution ledger prerequisites are missing: " + ", ".join(sorted(required - names)))
    if conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1").fetchone():
        raise RuntimeError("Ledger data is missing but execution receipts remain; restore the complete ledger.")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(OperationExecutionEvents)")}
    if columns != set(LEGACY_COLUMNS):
        raise RuntimeError("Legacy event columns changed; refusing a lossy archive.")
    for sql in objects.values():
        conn.execute(sql)
    conn.execute("INSERT INTO WorkbenchExecutionLedgerClock VALUES (1, 1, 1)")
    conn.execute(_capture_sql("1 = 1"))


objects = execution_ledger_objects
contract_issues = execution_ledger_contract_issues
