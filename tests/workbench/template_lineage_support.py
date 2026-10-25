"""Real batch/template/ledger fixtures, restricted to pytest temporary databases."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.infrastructure.calendar_periods_schema import install as install_calendar_periods
from core.infrastructure.machine_capabilities_schema import install as install_machine_capabilities
from core.infrastructure.material_stages_schema import install as install_material_stages
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.infrastructure.workbench_template_lineage_schema import install_template_lineage, template_lineage_objects
from core.models.workbench_batch import normalize_operation_input
from core.models.workbench_calibration import CalibrationQuery
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.scheduler.template_lineage_query import TemplateLineageQuery
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.operations import WorkbenchBatchOperationService
from core.services.workbench.calibration.service import WorkbenchCalibrationService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.execution_ledger_support import NOW, LedgerCase, install_current_content_storage


class TemplateLineageCase(LedgerCase):
    op_id: int


@pytest.fixture(name="ledger_case")
def ledger_fixture(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "template-lineage.sqlite"))
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parent / "fixtures" / "schema-v26.sql").read_text(encoding="utf-8"))
    install_current_content_storage(conn)
    # Main owns this frozen v26 fixture; unrelated current DDL cannot change the oracle.
    for name in reversed({**execution_ledger_objects(), **template_lineage_objects()}):
        row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if row is not None:
            if row[0] == "table":
                assert not conn.execute('SELECT 1 FROM "' + name + '" LIMIT 1').fetchone() or name == "WorkbenchExecutionLedgerClock"
            conn.execute('DROP ' + row[0].upper() + ' "' + name + '"')
    with TransactionManager(conn).transaction():
        install_metadata(conn)
        install_calendar_periods(conn)
        install_machine_capabilities(conn)
        install_material_stages(conn)
        install_plan_identity(conn)
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
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
    case.install()
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) VALUES ('P1',1,'T1','Turning','internal',0,1)")
    case.conn.commit()
    with TransactionManager(case.conn).transaction():
        install_template_lineage(case.conn)
    case.lineage_repo = WorkbenchTemplateLineageRepository(case.conn)
    case.template_id = case.conn.execute("SELECT id FROM PartOperations WHERE part_no='P1'").fetchone()[0]
    return case


def instance_for(case, op_id):
    row = case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
        (str(op_id),),
    ).fetchone()
    assert row is not None
    return case.lineage_repo.current_instances([row[0]])[row[0]]


def create(case, code="COPY-001", *, quantity=10):
    with TransactionManager(case.conn).transaction():
        case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',?)", (code, quantity))
        writer = TemplateLineageWriter(case.conn)
        facts = BatchFacts(case.conn).load()
        rows = [row for row in facts["PartOperations"] if row["part_no"] == "P1" and row["status"] == "active"]
        for template in writer.prepare_templates(rows, facts=facts):
            writer.copy_prepared_template(code, template)
    return case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id=? ORDER BY seq", (code,)).fetchone()[0]


def origin(case, op_id):
    ref = instance_for(case, op_id)["operation_ref"]
    row = next(case.lineage_repo.origin_rows([ref]))
    row.pop("_lineage_bytes", None)
    return row


def lineage(case, op_id):
    ref = instance_for(case, op_id)["operation_ref"]
    return TemplateLineageQuery(case.conn).read([ref])


def sync(case, code="COPY-001", *, key="template-sync-request-0001"):
    ref = case.ref("batch", code)
    service = WorkbenchBatchOperationService(case.conn)
    payload = service.normalize_sync({})
    return WorkbenchCommandService(case.conn).execute(request_key=key, action="batch.sync_confirm", context_ref=ref,
        normalized_input=payload, guard=lambda: service.sync_preview_normalized(ref), mutate=lambda _: service.sync_normalized(ref))


def edit(case, op_id, fields, *, key="template-edit-request-0001"):
    instance = instance_for(case, op_id)
    service = WorkbenchBatchOperationService(case.conn)
    ref = case.ref("batch", instance["batch_id"])
    payload = normalize_operation_input({"operation_ref": instance["operation_ref"], "fields": fields})
    return WorkbenchCommandService(case.conn).execute(request_key=key, action="batch.operation_update", context_ref=ref,
        normalized_input=payload, guard=lambda: service.prepare_update(ref, payload), mutate=service.apply_update)


def completed(case, hours, *, prefix="COPY", version=2):
    ids = [create(case, prefix + "-" + str(index).zfill(3)) for index in range(len(hours))]
    case.plan(version, ids)
    reports = []
    for index, (op_id, value) in enumerate(zip(ids, hours)):
        end = datetime(2026, 9, 9, 10) + timedelta(minutes=index)
        start = end - timedelta(hours=value * 10 + 1)
        reports.append(case.command("create", case.task(version, op_id), case.values(10,
            effective_processing_hours=value * 10, actual_start=start.isoformat(), actual_end=end.isoformat()))["data"]["rows"][0])
    return ids, reports


def calibration(case):
    service = WorkbenchCalibrationService(case.conn, as_of=NOW)
    with service.read_snapshot():
        return service.read(CalibrationQuery())
