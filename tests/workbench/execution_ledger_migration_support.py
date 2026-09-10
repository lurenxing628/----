"""Fixed v24 input for both the v25 step and backed-up upgrades to CURRENT."""

import sqlite3
from pathlib import Path

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_run_schema import workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects

V24_SCHEMA = Path(__file__).parent / "fixtures" / "schema-v24.sql"
V27_TABLES = (
    "WorkbenchTemplateLineageOrigins", "WorkbenchTemplateLineageEvents",
    "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialChanges",
    "WorkbenchTrialScenarios", "WorkbenchTrialScenarioRows",
)


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(conn):
    result = {}
    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [row[1] for row in conn.execute("PRAGMA table_info(" + quoted + ")")]
        types = ",".join('typeof("' + column.replace('"', '""') + '")' for column in columns)
        result[name] = sorted((tuple(row) for row in conn.execute(
            "SELECT *," + types + " FROM " + quoted)), key=repr)
    return result


def seed_v24(path):
    conn = connect(path)
    conn.executescript(V24_SCHEMA.read_text(encoding="utf-8"))
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert not (set(execution_ledger_objects()) | set(workbench_run_objects()) |
                set(template_lineage_objects()) | set(workbench_trial_objects())) & names
    set_schema_version(conn, 24)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('P1','Part','private retained note')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity,remark) VALUES ('B1','P1',10,'batch original')")
    conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source) "
                 "VALUES (37,'OP1','B1',1,'T1','Turning','internal')")
    conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (7,'old','success','{}')")
    conn.execute("INSERT INTO Schedule(id,version,op_id,machine_id,operator_id,start_time,end_time) "
                 "VALUES (81,7,37,'M1','O1','2026-09-09 22:30:00','2026-09-10 06:30:00')")
    for key, kind, status, stamp in (
        (11, "start", "processing", "2026-09-09 22:30:00"),
        (12, "finish", "completed", "2026-09-10 06:30:00"),
    ):
        conn.execute("""INSERT INTO OperationExecutionEvents
            (id,schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,
             event_type,reported_status,event_time,actual_machine_id,actual_operator_id,
             quantity_done,remark,created_by,idempotency_key,request_fingerprint,previous_state_revision,created_at)
            VALUES (?,7,81,37,'B1','schedule','adopted',?,?,?,'M1','O1',NULL,?,'legacy-user',?,?,?,?)""",
            (key, kind, status, stamp, sqlite3.Binary(b"\x00retained-legacy\xff"),
             "legacy-key-" + str(key), "legacy-fingerprint-" + str(key),
             "37:0:0" if key == 11 else "37:1:11", "2020-02-03 04:05:06"))
    conn.commit()
    return conn


def without_version(rows):
    return {key: value for key, value in rows.items() if key != "SchemaVersion"}
