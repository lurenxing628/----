"""Real batch/template/ledger fixtures, restricted to pytest temporary databases."""

from datetime import date, datetime, timedelta

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_calibration import CalibrationQuery
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.scheduler.template_lineage_query import TemplateLineageQuery
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.calibration.service import WorkbenchCalibrationService
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.execution_ledger_support import NOW, LedgerCase, current_database


class TemplateLineageCase(LedgerCase):
    op_id: int


@pytest.fixture(name="ledger_case")
def ledger_fixture(tmp_path):
    conn = current_database(tmp_path / "template-lineage.sqlite")
    with TransactionManager(conn).transaction():
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Lathe')")
        conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10)")
        case = TemplateLineageCase(conn)
        case.op_id = case.op()
    case.plan(1, [case.op_id])
    try:
        yield case
    finally:
        conn.close()


@pytest.fixture(name="lineage_case")
def lineage_case(ledger_case):
    case = ledger_case
    case.conn.execute(
        "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
        "VALUES ('P1',1,'T1','Turning','internal',0,1)"
    )
    case.conn.commit()
    case.lineage_repo = WorkbenchTemplateLineageRepository(case.conn)
    case.template_id = case.conn.execute("SELECT id FROM PartOperations WHERE part_no='P1'").fetchone()[0]
    return case


def instance_for(case, op_id):
    row = case.conn.execute(
        """SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
           FROM WorkbenchPlanSourceRefs r
           JOIN BatchOperations o ON o.id=CAST(r.source_key AS INTEGER) AND CAST(o.id AS TEXT)=r.source_key
           JOIN Batches b ON b.batch_id=o.batch_id
           LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
           LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
           WHERE r.kind='operation' AND r.active=1 AND r.source_key=?""",
        (str(op_id),),
    ).fetchone()
    assert row is not None
    return dict(row)


def create(case, code="COPY-001", *, quantity=10):
    with TransactionManager(case.conn).transaction():
        case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',?)", (code, quantity))
        writer = TemplateLineageWriter(case.conn)
        facts = BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat())).load()
        rows = [row for row in facts["PartOperations"] if row["part_no"] == "P1" and row["status"] == "active"]
        for template in writer.prepare_templates(rows, facts=facts):
            writer.copy_prepared_template(code, template)
    return case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id=? ORDER BY seq", (code,)).fetchone()[0]


def origin(case, op_id):
    ref = instance_for(case, op_id)["operation_ref"]
    return case.lineage_repo.origin_rows([ref])[0]


def lineage(case, op_id):
    ref = instance_for(case, op_id)["operation_ref"]
    return TemplateLineageQuery(case.conn).read([ref])


def completed(case, hours, *, prefix="COPY", version=2):
    ids = [create(case, prefix + "-" + str(index).zfill(3)) for index in range(len(hours))]
    case.plan(version, ids)
    reports = []
    for index, (op_id, value) in enumerate(zip(ids, hours)):
        end = datetime(2026, 9, 9, 10) + timedelta(minutes=index)
        start = end - timedelta(hours=value * 10 + 1)
        reports.append(
            case.command(
                "create",
                case.task(version, op_id),
                case.values(
                    10,
                    effective_processing_hours=value * 10,
                    actual_start=start.isoformat(),
                    actual_end=end.isoformat(),
                ),
            )["data"]["rows"][0]
        )
    return ids, reports


def calibration(case):
    service = WorkbenchCalibrationService(case.conn)
    with service.read_snapshot() as ledger_scope:
        return service.read(ledger_scope, CalibrationQuery(), as_of=NOW)
