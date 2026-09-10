"""Real batch/template/ledger fixtures, restricted to pytest temporary databases."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.infrastructure.workbench_template_lineage_schema import install, objects
from core.models.workbench_calibration import CalibrationQuery
from core.services.scheduler.batch_service import BatchService
from core.services.workbench.batch_operations import WorkbenchBatchOperationService
from core.services.workbench.calibration import WorkbenchCalibrationService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.template_lineage import TemplateLineageWriter
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.execution_ledger_support import NOW, LedgerCase


class TemplateLineageCase(LedgerCase):
    op_id: int


@pytest.fixture(name="ledger_case")
def ledger_fixture(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "template-lineage.sqlite"))
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parent / "fixtures" / "schema-v26.sql").read_text(encoding="utf-8"))
    # Main owns this frozen v26 fixture; unrelated current DDL cannot change the oracle.
    for name in reversed({**execution_ledger_objects(), **objects()}):
        row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if row is not None:
            if row[0] == "table":
                assert not conn.execute('SELECT 1 FROM "' + name + '" LIMIT 1').fetchone() or name == "WorkbenchExecutionLedgerClock"
            conn.execute('DROP ' + row[0].upper() + ' "' + name + '"')
    with TransactionManager(conn).transaction():
        install_metadata(conn)
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
        install(case.conn)
    case.batch_service = BatchService(case.conn)
    case.lineage_writer = TemplateLineageWriter(case.conn)
    case.lineage_repo = WorkbenchTemplateLineageRepository(case.conn)
    case.template_id = case.conn.execute("SELECT id FROM PartOperations WHERE part_no='P1'").fetchone()[0]
    return case


def create(case, code="COPY-001", *, quantity=10, rebuild=False):
    case.batch_service.create_batch_from_template(code, "P1", quantity, rebuild_ops=rebuild)
    return case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id=? ORDER BY seq", (code,)).fetchone()[0]


def origin(case, op_id):
    ref = case.lineage_repo.instance(op_id)["operation_ref"]
    return case.lineage_repo.origins([ref])[ref]


def lineage(case, op_id):
    ref = case.lineage_repo.instance(op_id)["operation_ref"]
    return TemplateLineageQuery(case.conn).read([ref])


def sync(case, code="COPY-001", *, key="template-sync-request-0001"):
    ref = case.ref("batch", code)
    service = WorkbenchBatchOperationService(case.conn)
    payload = {"strict_mode": False}
    return WorkbenchCommandService(case.conn).execute(request_key=key, action="batch.sync_confirm", context_ref=ref,
        normalized_input=payload, guard=lambda: service.sync_preview(ref, payload), mutate=lambda _: service.sync(ref, payload))


def edit(case, op_id, fields, *, key="template-edit-request-0001"):
    instance = case.lineage_repo.instance(op_id)
    service = WorkbenchBatchOperationService(case.conn)
    ref = case.ref("batch", instance["batch_id"])
    payload = {"operation_ref": instance["operation_ref"], "fields": fields}
    return WorkbenchCommandService(case.conn).execute(request_key=key, action="batch.operation_update", context_ref=ref,
        normalized_input=payload, guard=lambda: None, mutate=lambda _: service.update(ref, payload))


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
