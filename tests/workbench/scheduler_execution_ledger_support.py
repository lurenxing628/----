"""Real SQLite scheduler-ledger reads shared by the execution-ledger guard tests."""

from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.execution.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def plan_rows(conn, version):
    return [dict(row) for row in conn.execute("""SELECT s.id AS schedule_id, s.version, s.op_id, b.batch_id
        FROM Schedule s JOIN BatchOperations b ON b.id=s.op_id WHERE s.version=? ORDER BY s.op_id""", (version,))]


def read_facts(conn, version=1):
    """The guard's read: one formal plan's facts with that plan's ledger projections supplied, as the run input does."""
    rows = plan_rows(conn, version)
    refs = WorkbenchPlanIdentityRepository(conn).get_operation_refs(row["op_id"] for row in rows)
    projections = ExecutionLedgerReader(conn, current_plan_provider=current_execution_plan).project_operations(
        sorted({refs[row["op_id"]] for row in rows}))
    return ExecutionFactProvider(conn).facts_by_op_id_for_plan_rows(rows, execution_projections=projections)


def formal_rows(conn):
    tables = ("Schedule", "ScheduleHistory", "ScheduleVersionSeq", "BatchOperations")
    return {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY rowid")]
            for table in tables}
