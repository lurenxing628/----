"""Additive report-void facts. Installation belongs to an explicit migration."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql


def execution_void_objects():
    objects = {
        "WorkbenchProductionReportVoids": """CREATE TABLE WorkbenchProductionReportVoids (
            void_fact_ref TEXT PRIMARY KEY NOT NULL CHECK(length(void_fact_ref)=48 AND void_fact_ref NOT GLOB '*[^0-9a-f]*'),
            report_ref TEXT NOT NULL UNIQUE,
            original_revision_ref TEXT NOT NULL UNIQUE,
            reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
            local_operator TEXT NOT NULL CHECK(length(trim(local_operator)) > 0),
            declared_operator TEXT NOT NULL, recorded_at TEXT NOT NULL,
            request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(report_ref) REFERENCES WorkbenchProductionReports(report_ref),
            FOREIGN KEY(original_revision_ref) REFERENCES WorkbenchProductionReportRevisions(revision_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""",
        "wb_execution_voids_clock": """CREATE TRIGGER wb_execution_voids_clock AFTER INSERT ON WorkbenchProductionReportVoids
            BEGIN UPDATE WorkbenchExecutionLedgerClock SET revision=revision+1 WHERE singleton=1; END""",
        "wb_execution_voids_current_revision": """CREATE TRIGGER wb_execution_voids_current_revision BEFORE INSERT ON WorkbenchProductionReportVoids
            WHEN NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions r
                WHERE r.report_ref=NEW.report_ref AND r.revision_ref=NEW.original_revision_ref
                AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions later
                    WHERE later.report_ref=r.report_ref AND later.sequence>r.sequence))
            BEGIN SELECT RAISE(ABORT, 'report void requires current revision'); END""",
        "wb_execution_voided_no_revision": """CREATE TRIGGER wb_execution_voided_no_revision BEFORE INSERT ON WorkbenchProductionReportRevisions
            WHEN EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids v WHERE v.report_ref=NEW.report_ref)
            BEGIN SELECT RAISE(ABORT, 'voided report cannot be revised'); END""",
        "wb_execution_voids_no_replace": """CREATE TRIGGER wb_execution_voids_no_replace BEFORE INSERT ON WorkbenchProductionReportVoids
            WHEN EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids v WHERE v.void_fact_ref=NEW.void_fact_ref
                OR v.report_ref=NEW.report_ref OR v.original_revision_ref=NEW.original_revision_ref OR v.request_key=NEW.request_key)
            BEGIN SELECT RAISE(ABORT, 'execution void cannot be replaced'); END""",
    }
    for event in ("update", "delete"):
        name = "wb_execution_voids_no_" + event
        objects[name] = ("CREATE TRIGGER " + name + " BEFORE " + event.upper() +
                         " ON WorkbenchProductionReportVoids BEGIN SELECT RAISE(ABORT, 'execution ledger is append-only'); END")
    return objects


def execution_void_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_execution_void:" if name not in actual else "invalid_execution_void:") + name
            for name, sql in execution_void_objects().items()
            if name not in actual or _canonical_sql(sql) != _canonical_sql(actual[name] or "")]


def install_execution_voids(conn):
    if not conn.in_transaction:
        raise RuntimeError("Execution void installation requires the migration transaction.")
    objects = execution_void_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects):
        issues = execution_void_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial execution void facts: " + "; ".join(issues))
        return
    required = {"WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchExecutionLedgerClock", "WorkbenchCommandReceipts"}
    if not required <= names:
        raise RuntimeError("Execution void prerequisites are missing.")
    from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
    if execution_ledger_contract_issues(conn):
        raise RuntimeError("Execution ledger prerequisites do not match their schema contract.")
    if conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action='execution.report_void' LIMIT 1").fetchone():
        raise RuntimeError("Report void receipts remain without facts; restore the complete ledger.")
    for sql in objects.values():
        conn.execute(sql)
