"""Immutable projections of the original run archive."""

from core.models.enums import RUN_RESOURCE_VIEW_VALUES, enum_check, flag_check, nullable_time_us_check

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql

READ_MODEL_TABLES = (
    "WorkbenchRunAdmissionReadModels",
    "WorkbenchRunDecisionReadModels",
    "WorkbenchRunCandidateReadModels",
    "WorkbenchRunSideBatches",
    "WorkbenchRunOperationCatalog",
    "WorkbenchRunSideOperations",
    "WorkbenchRunSideResources",
)
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def objects():
    definitions = {
        "WorkbenchRunAdmissionReadModels": """CREATE TABLE WorkbenchRunAdmissionReadModels (
            run_ref {} PRIMARY KEY,
            scope_json TEXT NOT NULL, decision_json TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("run_ref")),
        "WorkbenchRunDecisionReadModels": """CREATE TABLE WorkbenchRunDecisionReadModels (
            run_ref {} PRIMARY KEY,
            header_json TEXT NOT NULL, context_json TEXT NOT NULL, memberships_json TEXT NOT NULL,
            calendar_json TEXT NOT NULL, official_json TEXT NOT NULL, process_json TEXT,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("run_ref")),
        "WorkbenchRunCandidateReadModels": """CREATE TABLE WorkbenchRunCandidateReadModels (
            candidate_ref {} PRIMARY KEY, run_ref TEXT NOT NULL,
            summary_json TEXT NOT NULL, preparation_json TEXT NOT NULL,
            completion_json TEXT NOT NULL, delivery_json TEXT NOT NULL, delivery_detail_json TEXT NOT NULL,
            arrangements_json TEXT NOT NULL,
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(_REF.format("candidate_ref")),
        "WorkbenchRunSideBatches": """CREATE TABLE WorkbenchRunSideBatches (
            run_ref {},
            side_key TEXT NOT NULL,
            batch_ref TEXT NOT NULL,
            batch_label TEXT,
            due_date TEXT,
            is_overdue INTEGER,
            delay_hours REAL,
            finish_time TEXT,
            finish_us INTEGER {finish_us},
            status TEXT NOT NULL,
            scheduled_count INTEGER NOT NULL,
            total_count INTEGER NOT NULL,
            deferred_count INTEGER NOT NULL,
            unplanned_count INTEGER NOT NULL,
            detail_json TEXT NOT NULL,
            PRIMARY KEY(run_ref, side_key, batch_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(
                _REF.format("run_ref"), finish_us=nullable_time_us_check("finish_us")),
        "WorkbenchRunOperationCatalog": """CREATE TABLE WorkbenchRunOperationCatalog (
            run_ref {},
            operation_ref TEXT NOT NULL,
            batch_ref TEXT,
            batch_label TEXT,
            sequence INTEGER,
            sequence_unknown INTEGER NOT NULL {sequence_unknown},
            op_id INTEGER NOT NULL,
            saved_machine_ref TEXT,
            label_json TEXT NOT NULL,
            PRIMARY KEY(run_ref, operation_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(
                _REF.format("run_ref"), sequence_unknown=flag_check("sequence_unknown")),
        "WorkbenchRunSideOperations": """CREATE TABLE WorkbenchRunSideOperations (
            run_ref {},
            side_key TEXT NOT NULL,
            operation_ref TEXT NOT NULL,
            arranged INTEGER NOT NULL {arranged},
            deferred INTEGER NOT NULL {deferred},
            allocation_state TEXT NOT NULL,
            is_remaining INTEGER NOT NULL {is_remaining},
            start_us INTEGER {start_us},
            end_us INTEGER {end_us},
            machine_ref TEXT,
            operator_ref TEXT,
            resource_refs_json TEXT NOT NULL,
            setup_hours REAL,
            required_hours REAL,
            arrangement_json TEXT,
            preparation_json TEXT NOT NULL,
            PRIMARY KEY(run_ref, side_key, operation_ref),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(
                _REF.format("run_ref"), start_us=nullable_time_us_check("start_us"), end_us=nullable_time_us_check("end_us"),
                arranged=flag_check("arranged"), deferred=flag_check("deferred"), is_remaining=flag_check("is_remaining")),
        "WorkbenchRunSideResources": """CREATE TABLE WorkbenchRunSideResources (
            run_ref {},
            side_key TEXT NOT NULL,
            resource_view TEXT NOT NULL {resource_view},
            payload_json TEXT NOT NULL,
            PRIMARY KEY(run_ref, side_key, resource_view),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref))""".format(
                _REF.format("run_ref"), resource_view=enum_check("resource_view", RUN_RESOURCE_VIEW_VALUES)),
        "idx_wb_run_input": "CREATE INDEX idx_wb_run_input ON WorkbenchRunJobs(input_ref)",
        "idx_wb_command_action_context_time": "CREATE INDEX idx_wb_command_action_context_time "
            "ON WorkbenchCommandReceipts(action,context_ref,committed_at_utc,request_key)",
        "idx_wb_run_candidate_model_run": "CREATE INDEX idx_wb_run_candidate_model_run "
            "ON WorkbenchRunCandidateReadModels(run_ref,candidate_ref)",
        "idx_wb_run_accepted": "CREATE INDEX idx_wb_run_accepted ON WorkbenchRunJobs(accepted_at,run_ref)",
        "idx_wb_run_started": "CREATE INDEX idx_wb_run_started ON WorkbenchRunJobs(started_at,run_ref)",
        "idx_wb_run_finished": "CREATE INDEX idx_wb_run_finished ON WorkbenchRunJobs(finished_at,run_ref)",
        "idx_wb_run_op_cat_batch": "CREATE INDEX idx_wb_run_op_cat_batch "
            "ON WorkbenchRunOperationCatalog(run_ref, batch_ref)",
        "idx_wb_run_side_ops_alloc": "CREATE INDEX idx_wb_run_side_ops_alloc "
            "ON WorkbenchRunSideOperations(run_ref, side_key, allocation_state)",
    }
    for table in READ_MODEL_TABLES:
        stem = table[len("Workbench"):].lower()
        for event in ("UPDATE", "DELETE"):
            name = "wb_" + stem + "_no_" + event.lower()
            definitions[name] = "CREATE TRIGGER " + name + " BEFORE " + event + " ON " + table + \
                " BEGIN SELECT RAISE(ABORT,'run read model is permanent'); END"
    return definitions


def contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_run_read_model:" if name not in actual else "invalid_run_read_model:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name])]
