"""AS-owned fixtures: actual SQLite, actual ledger, actual scheduling engine."""

from datetime import datetime

import pytest

from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_execution_void_schema import install_execution_voids
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.execution_ledger_support import LedgerCase, all_rows
from tests.workbench.identity_metadata_support import insert_row


class RunCase(LedgerCase):
    def batch(self, code, **patch):
        values = dict(batch_id=code, part_no="P1", quantity=3,
                      due_date="2026-09-25", ready_status="yes", priority="normal", status="pending")
        values.update(patch)
        insert_row(self.conn, "Batches", values)

    def operation(self, batch="B1", seq=1, **patch):
        values = dict(op_code=f"{batch}-{seq}", batch_id=batch, seq=seq, op_type_id="T1",
                      op_type_name="Turning", source="internal", setup_hours=0, unit_hours=0.25,
                      machine_id="M1", operator_id="O1", status="pending")
        values.update(patch)
        insert_row(self.conn, "BatchOperations", values)
        return self.conn.execute("SELECT id FROM BatchOperations WHERE op_code=?", (values["op_code"],)).fetchone()[0]

    def settings(self, *batch_ids, **patch):
        result = dict(batch_refs=[self.ref("batch", code) for code in (batch_ids or ("B1",))],
                      start_date="2026-09-09", end_date="2026-09-25", ready_check=True,
                      missing_resource_policy="auto_assign", completed_policy="preserve_actuals")
        result.update(patch)
        return result

    def projections(self, *batch_ids):
        rows = list(self.conn.execute("""SELECT r.ref,bo.batch_id,
            EXISTS(SELECT 1 FROM Schedule s WHERE s.op_id=bo.id) AS has_scope
            FROM WorkbenchPlanSourceRefs r JOIN BatchOperations bo ON CAST(bo.id AS TEXT)=r.source_key
            WHERE r.kind='operation' AND r.active=1 ORDER BY r.ref"""))
        refs = [row[0] for row in rows if not batch_ids or row[1] in batch_ids or row[2]]
        return ExecutionLedgerService(self.conn, clock=lambda: datetime(2026, 9, 10, 12)).project_operations(refs)

    def config(self, **values):
        for key, value in values.items():
            self.conn.execute("UPDATE ScheduleConfig SET config_value=? WHERE config_key=?", (str(value), key))
        self.conn.commit()


@pytest.fixture(name="run_case")
def run_case(schema_conn):
    conn = schema_conn
    conn.execute("BEGIN")
    install_metadata(conn)
    install_plan_identity(conn)
    install_execution_ledger(conn)
    install_execution_voids(conn)
    conn.commit()
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = RunCase(conn)
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    yield case


def unchanged(case, action):
    before, changes = all_rows(case.conn), case.conn.total_changes
    try:
        return action()
    finally:
        assert all_rows(case.conn) == before
        assert case.conn.total_changes == changes
