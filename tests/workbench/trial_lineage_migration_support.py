"""Fixed v26 storage with old execution facts and genuine persisted candidates."""

from datetime import datetime
from pathlib import Path

from flask import Flask

from core.infrastructure.migration_state import set_schema_version
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_schema_migration_support import connect
from tests.workbench.test_run_jobs_support import JobCase

FIXTURE_V26 = Path(__file__).parent / "fixtures" / "schema-v26.sql"


def seed_v26(path):
    conn = connect(path)
    conn.executescript(FIXTURE_V26.read_text(encoding="utf-8"))
    set_schema_version(conn, 26)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('P1','Part',?)", (b"old\x00metadata\xff",))
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.batch("B1")
    case.op_id = case.operation()
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.batch("B2")
    case.operation("B2")
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    with Flask(__name__).app_context():
        accepted = case.accept("v26-preserved-run-0001", case.settings("B2"))
    stamp = datetime.fromisoformat(accepted["data"]["accepted_at"])
    result = WorkbenchRunWorker(conn, clock=lambda: stamp).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    assert conn.execute("SELECT count(*) FROM WorkbenchRunCandidates").fetchone()[0] == 4
    conn.commit()
    return conn
