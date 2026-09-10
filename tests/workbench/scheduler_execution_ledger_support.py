"""Real SQLite scheduler fixtures with an explicit AJ ledger installation."""

import sqlite3

import pytest

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.execution_snapshot import build_execution_snapshot
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.plan_identity_support import load_v24_schema

PLAN_FIELDS = {"source_table": "schedule", "effective_plan_role": "adopted", "scenario_id": None}


def raw_connection(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "scheduler-ledger.sqlite"))
    conn.row_factory = sqlite3.Row
    load_v24_schema(conn)
    set_schema_version(conn, 24)
    conn.commit()
    return conn


@pytest.fixture(name="ledger_case")
def ledger_case(tmp_path):
    conn = raw_connection(tmp_path)
    conn.execute("BEGIN")
    install_metadata(conn)
    install_plan_identity(conn)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10)")
    case = LedgerCase(conn)
    case.op_id = case.op()
    case.plan(1, [case.op_id])
    yield case
    conn.close()


def install_case(conn):
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('LEDGER-TYPE','Ledger turning')")
    conn.execute("UPDATE Machines SET op_type_id='LEDGER-TYPE'")
    conn.execute("UPDATE BatchOperations SET op_type_id='LEDGER-TYPE'")
    conn.execute("INSERT OR IGNORE INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT OR IGNORE INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    conn.commit()
    conn.execute("BEGIN")
    install_metadata(conn)
    install_plan_identity(conn)
    install_execution_ledger(conn)
    conn.commit()
    return LedgerCase(conn)


def plan_rows(conn, version):
    return [dict(row) for row in conn.execute("""SELECT s.id AS schedule_id, s.version, s.op_id, b.batch_id
        FROM Schedule s JOIN BatchOperations b ON b.id=s.op_id WHERE s.version=? ORDER BY s.op_id""", (version,))]


def read_facts(conn, version=1):
    return ExecutionFactProvider(conn).facts_by_op_id_for_plan_rows(plan_rows(conn, version), PLAN_FIELDS)


def read_snapshot(conn, version=1):
    facts = read_facts(conn, version)
    return build_execution_snapshot(facts, list(facts))


def formal_rows(conn):
    tables = ("Schedule", "ScheduleHistory", "ScheduleVersionSeq", "ScheduleCandidate", "ScheduleCandidateRows",
              "ScheduleCandidateSelection", "BatchOperations", "OperationExecutionEvents")
    return {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY rowid")]
            for table in tables}
