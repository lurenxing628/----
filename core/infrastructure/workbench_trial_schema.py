"""Explicit trial installation; no legacy table or schema-version changes."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues

TRIAL_TABLES = ("WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialChanges",
                "WorkbenchTrialScenarios", "WorkbenchTrialScenarioRows")
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_trial_objects():
    objects = {
        "WorkbenchTrialDrafts": """CREATE TABLE WorkbenchTrialDrafts (
            draft_ref {} PRIMARY KEY, base_kind TEXT NOT NULL CHECK(base_kind IN ('plan_ref','candidate_ref')),
            base_ref {}, admission_json TEXT NOT NULL, admission_hash TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK(typeof(row_count)='integer' AND row_count>0),
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=1),
            status TEXT NOT NULL CHECK(status IN ('editing','saved','discarded')),
            validation_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            local_operator TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("draft_ref"), _REF.format("base_ref")),
        "WorkbenchTrialRows": """CREATE TABLE WorkbenchTrialRows (
            row_ref {} PRIMARY KEY, task_ref {} UNIQUE, draft_ref TEXT NOT NULL,
            operation_ref TEXT NOT NULL, source_task_ref TEXT, source_row_ref TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0),
            original_json TEXT NOT NULL, original_hash TEXT NOT NULL, current_json TEXT NOT NULL,
            UNIQUE(draft_ref,operation_ref), UNIQUE(draft_ref,ordinal),
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        )""".format(_REF.format("row_ref"), _REF.format("task_ref")),
        "WorkbenchTrialChanges": """CREATE TABLE WorkbenchTrialChanges (
            change_ref {} PRIMARY KEY, draft_ref TEXT NOT NULL, task_ref TEXT NOT NULL,
            revision INTEGER NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            validation_json TEXT NOT NULL, recorded_at TEXT NOT NULL, local_operator TEXT NOT NULL,
            request_key TEXT NOT NULL UNIQUE, UNIQUE(draft_ref,revision),
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(task_ref) REFERENCES WorkbenchTrialRows(task_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("change_ref")),
        "WorkbenchTrialScenarios": """CREATE TABLE WorkbenchTrialScenarios (
            scenario_ref {} PRIMARY KEY, draft_ref TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
            saved_at TEXT NOT NULL, local_operator TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY(draft_ref) REFERENCES WorkbenchTrialDrafts(draft_ref),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(_REF.format("scenario_ref")),
        "WorkbenchTrialScenarioRows": """CREATE TABLE WorkbenchTrialScenarioRows (
            row_ref {} PRIMARY KEY, task_ref {} UNIQUE, scenario_ref TEXT NOT NULL,
            source_row_ref TEXT NOT NULL, payload_json TEXT NOT NULL,
            UNIQUE(scenario_ref,source_row_ref),
            FOREIGN KEY(scenario_ref) REFERENCES WorkbenchTrialScenarios(scenario_ref),
            FOREIGN KEY(source_row_ref) REFERENCES WorkbenchTrialRows(row_ref)
        )""".format(_REF.format("row_ref"), _REF.format("task_ref")),
        "idx_wb_trial_status": "CREATE INDEX idx_wb_trial_status ON WorkbenchTrialDrafts(status,updated_at,draft_ref)",
    }
    for table in TRIAL_TABLES:
        events = ("DELETE",) if table in TRIAL_TABLES[:2] else ("UPDATE", "DELETE")
        for event in events:
            name = "wb_" + table[9:].lower() + "_no_" + event.lower()
            objects[name] = f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'trial evidence is permanent'); END"
    for table, keys in ((TRIAL_TABLES[0], ("draft_ref", "base_kind", "base_ref", "admission_json", "admission_hash", "row_count", "created_at", "local_operator", "request_key")),
                        (TRIAL_TABLES[1], ("row_ref", "task_ref", "draft_ref", "operation_ref", "source_task_ref", "source_row_ref", "ordinal", "original_json", "original_hash"))):
        name = "wb_" + table[9:].lower() + "_identity"
        objects[name] = "CREATE TRIGGER {} BEFORE UPDATE ON {} WHEN {} BEGIN SELECT RAISE(ABORT,'trial baseline is immutable'); END".format(
            name, table, " OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in keys))
    objects["wb_trial_transition"] = """CREATE TRIGGER wb_trial_transition BEFORE UPDATE ON WorkbenchTrialDrafts
        WHEN OLD.status<>'editing' OR NEW.revision<>OLD.revision+1
        BEGIN SELECT RAISE(ABORT,'invalid trial transition'); END"""
    objects["wb_trial_closed_rows"] = """CREATE TRIGGER wb_trial_closed_rows BEFORE UPDATE ON WorkbenchTrialRows
        WHEN (SELECT status FROM WorkbenchTrialDrafts WHERE draft_ref=OLD.draft_ref)<>'editing'
        BEGIN SELECT RAISE(ABORT,'closed trial is immutable'); END"""
    return objects


def workbench_trial_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_trial_schema:" if name not in actual else "invalid_trial_schema:") + name
            for name, sql in workbench_trial_objects().items()
            if name not in actual or _canonical_sql(sql) != _canonical_sql(actual[name] or "")]


def install_workbench_trial_schema(conn):
    if not conn.in_transaction:
        raise RuntimeError("Trial installation requires the caller's migration transaction")
    objects = workbench_trial_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects):
        issues = workbench_trial_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial trial schema: " + "; ".join(issues))
        return
    if not {"WorkbenchCommandReceipts", "WorkbenchPlanSourceRefs"} <= names:
        raise RuntimeError("Trial identity/receipt prerequisites are missing")
    issues = workbench_metadata_contract_issues(conn) + workbench_plan_identity_contract_issues(conn)
    if issues:
        raise RuntimeError("Trial prerequisites are incomplete: " + "; ".join(issues))
    if conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action IN ('trial.create','trial.change','trial.save','trial.discard') LIMIT 1").fetchone():
        raise RuntimeError("Trial receipts remain without their ledger; restore a complete backup")
    for sql in objects.values():
        conn.execute(sql)


objects = workbench_trial_objects
contract_issues = workbench_trial_contract_issues
install = install_workbench_trial_schema
