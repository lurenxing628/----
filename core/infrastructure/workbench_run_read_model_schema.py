"""Immutable projections of the original run archive, installed by v41 only."""

from .schema_structure import SchemaStructure, schema_objects
from .workbench_metadata_schema import canonical_sql
from .workbench_run_schema import workbench_run_contract_issues

READ_MODEL_TABLES = ("WorkbenchRunAdmissionReadModels", "WorkbenchRunDecisionReadModels", "WorkbenchRunCandidateReadModels")
PROJECTION_VERSION = "decision-read-v1"
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def objects():
    definitions = {
        "WorkbenchRunAdmissionReadModels": """CREATE TABLE WorkbenchRunAdmissionReadModels (
            run_ref {} PRIMARY KEY,
            projection_version TEXT NOT NULL, scope_json TEXT NOT NULL, decision_json TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("run_ref")),
        "WorkbenchRunDecisionReadModels": """CREATE TABLE WorkbenchRunDecisionReadModels (
            run_ref {} PRIMARY KEY, projection_version TEXT NOT NULL,
            header_json TEXT NOT NULL, context_json TEXT NOT NULL, memberships_json TEXT NOT NULL,
            calendar_json TEXT NOT NULL, official_json TEXT NOT NULL, process_json TEXT,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("run_ref")),
        "WorkbenchRunCandidateReadModels": """CREATE TABLE WorkbenchRunCandidateReadModels (
            candidate_ref {} PRIMARY KEY, run_ref TEXT NOT NULL,
            projection_version TEXT NOT NULL, summary_json TEXT NOT NULL, preparation_json TEXT NOT NULL,
            completion_json TEXT NOT NULL, delivery_json TEXT NOT NULL, delivery_detail_json TEXT NOT NULL,
            arrangements_json TEXT NOT NULL,
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("candidate_ref")),
        "idx_wb_run_input": "CREATE INDEX idx_wb_run_input ON WorkbenchRunJobs(input_ref)",
        "idx_wb_command_action_context_time": "CREATE INDEX idx_wb_command_action_context_time "
            "ON WorkbenchCommandReceipts(action,context_ref,committed_at_utc,request_key)",
        "idx_wb_run_candidate_model_run": "CREATE INDEX idx_wb_run_candidate_model_run "
            "ON WorkbenchRunCandidateReadModels(run_ref,candidate_ref)",
        "idx_wb_run_accepted": "CREATE INDEX idx_wb_run_accepted ON WorkbenchRunJobs(accepted_at,run_ref)",
        "idx_wb_run_started": "CREATE INDEX idx_wb_run_started ON WorkbenchRunJobs(started_at,run_ref)",
        "idx_wb_run_finished": "CREATE INDEX idx_wb_run_finished ON WorkbenchRunJobs(finished_at,run_ref)",
    }
    for table in READ_MODEL_TABLES:
        stem = table[len("Workbench"):].lower()
        for event in ("UPDATE", "DELETE"):
            name = "wb_" + stem + "_no_" + event.lower()
            definitions[name] = "CREATE TRIGGER " + name + " BEFORE " + event + " ON " + table + \
                " BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END"
    return definitions


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return [("missing_run_read_model:" if name not in actual else "invalid_run_read_model:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "")]


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Run read models require the caller's migration transaction.")
    structure = SchemaStructure(conn)
    definitions = objects()
    if structure.objects.keys() & definitions.keys():
        issues = contract_issues(conn, structure=structure)
        if issues:
            raise RuntimeError("Cannot repair partial run read models: " + "; ".join(issues))
        return
    issues = workbench_run_contract_issues(conn, structure=structure, allow_legacy=False)
    if not structure.has_table("WorkbenchCommandReceipts"):
        issues.append("missing_table:WorkbenchCommandReceipts")
    if issues:
        raise RuntimeError("Run read model prerequisites are incomplete: " + "; ".join(issues))
    for sql in definitions.values():
        conn.execute(sql)
