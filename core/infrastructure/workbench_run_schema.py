"""Explicit run-ledger schema and contract validation."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.models.enums import (
    BATCH_OPERATION_STATUS_VALUES,
    BATCH_PRIORITY_VALUES,
    BATCH_STATUS_VALUES,
    READY_STATUS_VALUES,
    RUN_STAGE_VALUES,
    RUN_STATE_VALUES,
    RUN_TERMINAL_STATE_VALUES,
    SOURCE_TYPE_VALUES,
    RunStage,
    RunState,
    enum_check,
    enum_predicate,
    flag_check,
    nullable_enum_check,
    time_us_check,
)

from .schema_structure import SchemaStructure

RUN_TABLES = (
    "WorkbenchRunJobs",
    "WorkbenchRunReceipts",
    "WorkbenchRunCandidates",
    "WorkbenchRunCandidateTasks",
    "WorkbenchRunBatches",
    "WorkbenchRunOperations",
)
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def workbench_run_objects():
    objects = {
        "WorkbenchRunJobs": """CREATE TABLE WorkbenchRunJobs (
            run_ref {} PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
            input_ref TEXT NOT NULL, normalized_input_json TEXT NOT NULL,
            revisions_json TEXT NOT NULL, conditions_archive_json TEXT NOT NULL,
            execution_json TEXT NOT NULL, baseline_json TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            state TEXT NOT NULL {state},
            stage TEXT NOT NULL {stage},
            executor_ref TEXT, started_at TEXT, finished_at TEXT, error_json TEXT,
            CHECK((state='{queued}' AND {queued_stage} AND executor_ref IS NULL
                   AND started_at IS NULL AND finished_at IS NULL)
               OR (state='{running}' AND {running_stage} AND executor_ref IS NOT NULL
                   AND started_at IS NOT NULL AND finished_at IS NULL)
               OR ({terminal} AND stage='{finished}' AND finished_at IS NOT NULL)),
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""".format(
            _REF.format("run_ref"), state=enum_check("state", RUN_STATE_VALUES), stage=enum_check("stage", RUN_STAGE_VALUES),
            queued=RunState.QUEUED.value, running=RunState.RUNNING.value, finished=RunStage.FINISHED.value,
            queued_stage=enum_predicate("stage", (RunStage.QUEUED.value, RunStage.AWAITING_RECONCILIATION.value)),
            running_stage=enum_predicate("stage", (RunStage.COMPUTING.value, RunStage.AWAITING_RECONCILIATION.value)),
            terminal=enum_predicate("state", RUN_TERMINAL_STATE_VALUES)),
        "WorkbenchRunReceipts": """CREATE TABLE WorkbenchRunReceipts (
            receipt_ref {} PRIMARY KEY, run_ref TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL {state},
            result_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("receipt_ref"), state=enum_check("state", RUN_TERMINAL_STATE_VALUES)),
        "WorkbenchRunCandidates": """CREATE TABLE WorkbenchRunCandidates (
            candidate_ref {} PRIMARY KEY, run_ref TEXT NOT NULL, candidate_key TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK(typeof(sequence)='integer' AND sequence>=0),
            task_count INTEGER NOT NULL CHECK(typeof(task_count)='integer' AND task_count>=0),
            artifact_json TEXT NOT NULL, UNIQUE(run_ref,candidate_key), UNIQUE(run_ref,sequence),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("candidate_ref")),
        "WorkbenchRunCandidateTasks": """CREATE TABLE WorkbenchRunCandidateTasks (
            row_ref {} PRIMARY KEY,
            candidate_ref TEXT NOT NULL,
            operation_ref TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0),
            op_id INTEGER NOT NULL,
            source TEXT NOT NULL {source},
            machine_id TEXT,
            operator_id TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            start_us INTEGER NOT NULL {start_us},
            end_us INTEGER NOT NULL {end_us},
            is_point_event INTEGER NOT NULL,
            locked INTEGER NOT NULL {locked},
            CHECK(start_us <= end_us),
            CHECK(is_point_event = (start_us = end_us)),
            UNIQUE(candidate_ref, ordinal),
            UNIQUE(candidate_ref, operation_ref),
            FOREIGN KEY(candidate_ref) REFERENCES WorkbenchRunCandidates(candidate_ref),
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref)
        )""".format(_REF.format("row_ref"), source=enum_check("source", SOURCE_TYPE_VALUES),
                     start_us=time_us_check("start_us"), end_us=time_us_check("end_us"), locked=flag_check("locked")),
        "WorkbenchRunBatches": """CREATE TABLE WorkbenchRunBatches (
            run_ref {},
            batch_ref {},
            batch_id TEXT NOT NULL,
            part_no TEXT,
            part_ref TEXT,
            part_name TEXT,
            quantity INTEGER,
            due_date TEXT,
            priority TEXT {priority},
            ready_status TEXT {ready_status},
            ready_date TEXT,
            status TEXT {status},
            PRIMARY KEY(run_ref, batch_ref),
            UNIQUE(run_ref, batch_id),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("run_ref"), _REF.format("batch_ref"),
                     priority=nullable_enum_check("priority", BATCH_PRIORITY_VALUES),
                     ready_status=nullable_enum_check("ready_status", READY_STATUS_VALUES),
                     status=nullable_enum_check("status", BATCH_STATUS_VALUES)),
        "WorkbenchRunOperations": """CREATE TABLE WorkbenchRunOperations (
            run_ref {},
            operation_ref {},
            op_id INTEGER NOT NULL,
            op_code TEXT,
            batch_id TEXT NOT NULL,
            batch_ref TEXT,
            piece_id TEXT,
            seq INTEGER,
            op_type_id TEXT,
            op_type_name TEXT,
            op_type_ref TEXT,
            op_type_label TEXT,
            source TEXT {source},
            setup_hours REAL,
            unit_hours REAL,
            ext_days REAL,
            machine_id TEXT,
            machine_ref TEXT,
            machine_label TEXT,
            operator_id TEXT,
            operator_ref TEXT,
            operator_label TEXT,
            supplier_id TEXT,
            supplier_ref TEXT,
            supplier_label TEXT,
            status TEXT {status},
            PRIMARY KEY(run_ref, operation_ref),
            UNIQUE(run_ref, op_id),
            FOREIGN KEY(run_ref) REFERENCES WorkbenchRunJobs(run_ref)
        )""".format(_REF.format("run_ref"), _REF.format("operation_ref"),
                     source=nullable_enum_check("source", SOURCE_TYPE_VALUES),
                     status=nullable_enum_check("status", BATCH_OPERATION_STATUS_VALUES)),
        "idx_wb_run_state": "CREATE INDEX idx_wb_run_state ON WorkbenchRunJobs(state,accepted_at,run_ref)",
    }
    for table in RUN_TABLES:
        stem = table[len("Workbench"):].lower()
        for event in (("DELETE",) if table == "WorkbenchRunJobs" else ("UPDATE", "DELETE")):
            name = "wb_" + stem + "_no_" + event.lower()
            objects[name] = f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'run ledger is permanent'); END"
    immutable = (
        "run_ref",
        "request_key",
        "input_ref",
        "normalized_input_json",
        "revisions_json",
        "conditions_archive_json",
        "execution_json",
        "baseline_json",
        "accepted_at",
    )
    objects["wb_run_admission_immutable"] = """CREATE TRIGGER wb_run_admission_immutable
        BEFORE UPDATE ON WorkbenchRunJobs WHEN {}
        BEGIN SELECT RAISE(ABORT,'run admission is immutable'); END""".format(" OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in immutable))
    objects["wb_run_state_transition"] = f"""CREATE TRIGGER wb_run_state_transition
        BEFORE UPDATE ON WorkbenchRunJobs WHEN
        {enum_predicate('OLD.state', RUN_TERMINAL_STATE_VALUES)} OR
        NOT (NEW.state=OLD.state
             OR (OLD.state='{RunState.QUEUED.value}' AND {enum_predicate('NEW.state', (RunState.RUNNING.value, RunState.INTERRUPTED.value))})
             OR (OLD.state='{RunState.RUNNING.value}' AND {enum_predicate('NEW.state', RUN_TERMINAL_STATE_VALUES)}))
        BEGIN SELECT RAISE(ABORT,'invalid run transition'); END"""
    return objects


def workbench_run_contract_issues(structure: SchemaStructure):
    """SELECT only, including when the ledger is absent or only partly present."""
    actual = structure.sql
    return [("missing_run_schema:" if name not in actual else "invalid_run_schema:") + name
            for name, sql in workbench_run_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
