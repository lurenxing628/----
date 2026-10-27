"""Explicit run-ledger schema and contract validation."""

from core.infrastructure.workbench_metadata_schema import canonical_sql

from .schema_structure import schema_objects

RUN_TABLES = ("WorkbenchRunJobs", "WorkbenchRunReceipts", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks")
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_run_objects():
    objects = {
        "WorkbenchRunJobs": """CREATE TABLE WorkbenchRunJobs (
            run_ref {} PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
            input_ref TEXT NOT NULL, normalized_input_json TEXT NOT NULL,
            facts_json TEXT NOT NULL, execution_json TEXT NOT NULL,
            baseline_json TEXT NOT NULL, accepted_at TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('queued','running','complete','partial','failed','interrupted')),
            stage TEXT NOT NULL CHECK(stage IN ('queued','computing','finished','awaiting_reconciliation')),
            executor_ref TEXT, started_at TEXT, finished_at TEXT, error_json TEXT,
            CHECK((state='queued' AND stage IN ('queued','awaiting_reconciliation') AND executor_ref IS NULL
                   AND started_at IS NULL AND finished_at IS NULL)
               OR (state='running' AND stage IN ('computing','awaiting_reconciliation') AND executor_ref IS NOT NULL
                   AND started_at IS NOT NULL AND finished_at IS NULL)
               OR (state IN ('complete','partial','failed','interrupted') AND stage='finished' AND finished_at IS NOT NULL)),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("run_ref")),
        "WorkbenchRunReceipts": """CREATE TABLE WorkbenchRunReceipts (
            receipt_ref {} PRIMARY KEY, run_ref TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL CHECK(state IN ('complete','partial','failed','interrupted')),
            result_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("receipt_ref")),
        "WorkbenchRunCandidates": """CREATE TABLE WorkbenchRunCandidates (
            candidate_ref {} PRIMARY KEY, run_ref TEXT NOT NULL, candidate_key TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>=0),
            status TEXT NOT NULL CHECK(status='completed'),
            task_count INTEGER NOT NULL CHECK(typeof(task_count)='integer' AND task_count>=0),
            artifact_json TEXT NOT NULL, UNIQUE(run_ref,candidate_key), UNIQUE(run_ref,sequence),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("candidate_ref")),
        "WorkbenchRunCandidateTasks": """CREATE TABLE WorkbenchRunCandidateTasks (
            row_ref {} PRIMARY KEY, candidate_ref TEXT NOT NULL, operation_ref TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0),
            payload_json TEXT NOT NULL, UNIQUE(candidate_ref,operation_ref), UNIQUE(candidate_ref,ordinal),
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        )""".format(_REF.format("row_ref")),
        "idx_wb_run_state": "CREATE INDEX idx_wb_run_state ON WorkbenchRunJobs(state,accepted_at,run_ref)",
    }
    for table in RUN_TABLES:
        stem = table[len("Workbench"):].lower()
        for event in (("DELETE",) if table == "WorkbenchRunJobs" else ("UPDATE", "DELETE")):
            name = "wb_" + stem + "_no_" + event.lower()
            objects[name] = f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END"
    immutable = ("run_ref", "request_key", "input_ref", "normalized_input_json", "facts_json", "execution_json", "baseline_json", "accepted_at")
    objects["wb_run_admission_immutable"] = """CREATE TRIGGER wb_run_admission_immutable
        BEFORE UPDATE ON WorkbenchRunJobs WHEN {}
        BEGIN SELECT RAISE(ABORT,'run admission is immutable'); END""".format(" OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in immutable))
    objects["wb_run_state_transition"] = """CREATE TRIGGER wb_run_state_transition
        BEFORE UPDATE ON WorkbenchRunJobs WHEN
        OLD.state IN ('complete','partial','failed','interrupted') OR
        NOT (NEW.state=OLD.state OR (OLD.state='queued' AND NEW.state IN ('running','interrupted'))
             OR (OLD.state='running' AND NEW.state IN ('complete','partial','failed','interrupted')))
        BEGIN SELECT RAISE(ABORT,'invalid run transition'); END"""
    return objects


def workbench_run_contract_issues(conn, *, structure=None):
    """SELECT only, including when the ledger is absent or only partly present."""
    actual = schema_objects(conn, structure=structure)
    return [("missing_run_schema:" if name not in actual else "invalid_run_schema:") + name
            for name, sql in workbench_run_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
