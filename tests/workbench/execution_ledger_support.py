"""Dedicated real temporary SQLite fixtures. No production application imports."""

import sqlite3
from datetime import datetime

import pytest

from core.infrastructure.database import ensure_schema
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandOutcome
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.execution.production_report import WorkbenchProductionReportService
from core.shared.strict_json import canonical_json
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests._support.paths import REPO_ROOT

NOW = datetime(2026, 9, 10, 12)
START, END = "2026-09-09T08:00:00", "2026-09-09T10:00:00"
PLAN_INTENT = {"reason": "台账夹具正式计划", "declared_operator": "fixture-operator"}


def current_database(path):
    """A fixture database built exactly as production creates a new one."""
    ensure_schema(str(path), schema_path=str(REPO_ROOT / "schema.sql"))
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def official_plan_ref(conn, version):
    return conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=? AND active=1",
                        (version,)).fetchone()[0]


def publish_official_plan(conn, version, rows, *, adopted_at=START, operator="local-os-user"):
    """Publish an official version as a candidate adoption does: version, audit, rows and receipt.

    ``rows`` are Schedule rows (op_id, machine_id, operator_id, start_time, end_time). The adopted
    candidate is not part of these fixtures, so readers record the legal archived-source gap for it.
    The caller owns the transaction.
    """
    candidate_ref, run_ref = format(0xC0000000 + version, "048x"), format(0xA0000000 + version, "048x")
    request_key = "fixture-plan-adopt-" + format(version, "04d")
    previous = conn.execute("SELECT max(version) FROM ScheduleHistory WHERE version<?", (version,)).fetchone()[0]
    baseline_ref = official_plan_ref(conn, previous) if previous is not None else None
    proof = {"proof_version": "content_refs_v1", "candidate_ref": candidate_ref, "run_ref": run_ref,
             "baseline_ref": baseline_ref, "baseline_version": previous}
    times = [row[key] for row in rows for key in ("start_time", "end_time")]
    audit = {"source": "workbench_candidate_adoption", "request_key": request_key, "candidate_ref": candidate_ref,
             "run_ref": run_ref, "proof": proof, **PLAN_INTENT, "baseline_ref": baseline_ref,
             "baseline_version": previous, "version": version, "validation": "valid", "row_count": len(rows),
             "application_operator": operator, "adopted_at": adopted_at, "is_simulation": False,
             "material_policy": {"ready_check": True, "material_strategy": "strict",
                                 "start_date": min(times)[:10], "end_date": max(times)[:10]},
             "deferred_operation_ids": []}
    batches = {conn.execute("SELECT batch_id FROM BatchOperations WHERE id=?", (row["op_id"],)).fetchone()[0] for row in rows}
    conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (?)", (version,))
    conn.execute("INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary,"
                 "schedule_time,created_by) VALUES (?,'manual',?,?,'success',?,?,?)",
                 (version, len(batches), len(rows), canonical_json(audit), adopted_at, operator))
    for row in rows:
        conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (?,?,?,?,?,?)",
                     (version, row["op_id"], row["machine_id"], row["operator_id"], row["start_time"], row["end_time"]))
    plan_ref = official_plan_ref(conn, version)
    official = {"plan_ref": plan_ref, "version": version, "kind": "official", "is_current_official": True,
                "display_name": "正式计划 v" + str(version), "baseline_ref": baseline_ref, "completeness": "complete",
                "capabilities": {"view": True, "edit_draft": False, "adopt": False, "report_actual": True},
                "blocked_reasons": [], "source_run_ref": run_ref}
    WorkbenchCommandRepository(conn).insert(
        request_key=request_key, receipt_ref=format(0xB0000000 + version, "032x"), action="scheduling.candidate.adopt",
        context_ref=candidate_ref, input_json=content_text({"confirm": True, **PLAN_INTENT}, json_input=True),
        outcome=WorkbenchCommandOutcome("committed", {"candidate_ref": candidate_ref, "run_ref": run_ref,
                                                      "official_plan": official, "row_count": len(rows)}))
    return plan_ref


class LedgerCase:
    def __init__(self, conn):
        self.conn = conn
        self.ledger = ExecutionLedgerService(conn, clock=lambda: NOW)
        self.writer = WorkbenchProductionReportService(conn, clock=lambda: NOW, actor_provider=lambda: "local-os-user")
        self.count = 0

    def op(self, code="OP1", *, seq=1, piece=None, batch="B1"):
        return self.conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,piece_id,op_type_id,op_type_name,source)
            VALUES (?,?,?,?,'T1','Turning','internal')""", (code, batch, seq, piece)).lastrowid

    def plan(self, version, ids, *, start=START, end=END):
        publish_official_plan(self.conn, version, [{"op_id": op_id, "machine_id": "M1", "operator_id": "O1",
                                                    "start_time": start, "end_time": end} for op_id in ids])
        self.conn.commit()

    def plan_ref(self, version):
        return official_plan_ref(self.conn, version)

    def task(self, version, op_id):
        return self.conn.execute("""SELECT t.ref FROM WorkbenchTaskRefs t JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref WHERE p.kind='official' AND p.version=?
            AND r.operation_id=? AND r.active=1""", (version, op_id)).fetchone()[0]

    def ref(self, kind, key):
        return self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()[0]

    def task_projection(self, task_ref):
        """按任务所属计划读出该工序的执行投影；生产只按工序批量读投影，没有按任务编号单读的入口。"""
        with self.ledger.read_snapshot():
            task = self.ledger.repo.task_headers([task_ref])[task_ref]
            facts = self.ledger.load_many([task["operation_ref"]], comparison_plan_ref=task["plan_ref"])
            return self.ledger.project_loaded(facts)[0]

    def report_projection(self, report_ref):
        """从所属工序的执行投影里取出这条报工；生产只按工序批量读投影，没有按报工单号单读的入口。"""
        with self.ledger.read_snapshot():
            operation_ref = self.ledger.report_header(report_ref=report_ref)["operation_ref"]
            projection = self.ledger.project_operations([operation_ref])[0]
        return next(report for report in projection.reports if report.report_ref == report_ref)

    def values(self, quantity=1, **patch):
        return {"actual_start": START, "actual_end": END, "completed_quantity": quantity,
                "effective_processing_hours": 1.5, "actual_machine_ref": self.ref("machine", "M1"),
                "actual_operator_ref": self.ref("operator", "O1"), "remark": "", **patch}

    def command(self, action, ref, payload, *, key=None, validate_context=None):
        self.count += 1
        return self.writer.execute(action, ref, payload, request_key=key or f"ledger-command-{self.count:08d}",
            validate_context=validate_context or (lambda *_: None))

@pytest.fixture(name="ledger_case")
def ledger_case(tmp_path):
    conn = current_database(tmp_path / "execution-ledger.sqlite")
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


def all_rows(conn):
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {table: [tuple(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}
