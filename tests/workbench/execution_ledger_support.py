"""Dedicated real temporary SQLite fixtures. No production application imports."""

import sqlite3
from datetime import datetime

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.sqlite_udf import register_schedule_time_sql_functions
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
    register_schedule_time_sql_functions(conn)
    return conn


def official_plan_ref(conn, version):
    return conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=? AND active=1",
                        (version,)).fetchone()[0]


def _record_candidate_adoption_source(conn, version, rows, *, candidate_ref, run_ref, baseline_ref, previous, adopted_at, batches):
    from core.models.workbench_preflight import normalize_preflight_input
    from core.services.workbench.facts.production_capture import ProductionFactsCapture

    run_request_key = "fixture-run-admit-" + format(version, "04d")
    input_ref = "fixture-input-" + format(version, "04d")
    times = [row[key] for row in rows for key in ("start_time", "end_time")]
    batch_refs = {
        batch_id: conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key=? AND active=1",
            (batch_id,),
        ).fetchone()[0]
        for batch_id in sorted(batches)
    }
    settings = normalize_preflight_input({
        "batch_refs": sorted(batch_refs.values()),
        "start_date": min(times)[:10],
        "end_date": max(times)[:10],
        "ready_check": True,
        "missing_resource_policy": "auto_assign",
        "completed_policy": "preserve_actuals",
    })
    facts_text = ProductionFactsCapture(conn).content()
    if previous is None:
        baseline = {"plan_ref": None, "version": None, "rows": []}
        prev_op_ids = set()
    else:
        prev_rows = [
            dict(r)
            for r in conn.execute(
                'SELECT r.id, r.op_id, r.machine_id, r.operator_id, +r.start_time AS start_time, '
                '+r.end_time AS end_time, r.lock_status, r.version, +r.created_at AS created_at '
                'FROM "Schedule" r WHERE r.version <= ? ORDER BY r.id ASC, r.rowid ASC',
                (previous,),
            )
        ]
        baseline = {
            "plan_ref": baseline_ref,
            "version": previous,
            "rows": [r for r in prev_rows if r["version"] == previous],
        }
        prev_op_ids = {r["op_id"] for r in prev_rows}
    op_rows = list(
        conn.execute(
            "SELECT bo.id AS op_id, bo.batch_id, bo.op_type_id, s.ref AS op_ref "
            "FROM BatchOperations bo JOIN WorkbenchPlanSourceRefs s "
            "ON s.kind='operation' AND s.active=1 AND CAST(bo.id AS TEXT)=s.source_key"
        )
    )
    selected_ops = [r for r in op_rows if r["batch_id"] in batches]
    exec_op_refs = sorted({r["op_ref"] for r in op_rows if r["batch_id"] in batches or r["op_id"] in prev_op_ids})
    ledger_svc = ExecutionLedgerService(conn, clock=lambda: NOW)
    with ledger_svc.read_snapshot() as scope:
        projections = [
            item
            for start_idx in range(0, len(exec_op_refs), 5000)
            for item in ledger_svc.project_operations(scope, exec_op_refs[start_idx : start_idx + 5000])
        ]
    conn.execute(
        "INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,facts_json,"
        "execution_json,baseline_json,accepted_at,started_at,finished_at,state,stage) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,'complete','finished')",
        (
            run_ref,
            run_request_key,
            input_ref,
            canonical_json(settings),
            facts_text,
            canonical_json([item.to_dict() for item in projections]),
            canonical_json(baseline),
            adopted_at,
            adopted_at,
            adopted_at,
        ),
    )
    WorkbenchCommandRepository(conn).insert(
        request_key=run_request_key,
        receipt_ref=format(0xD0000000 + version, "032x"),
        action="scheduling.run",
        context_ref=input_ref,
        input_json=content_text({"input_ref": input_ref}, json_input=True),
        outcome=WorkbenchCommandOutcome("committed", {"run_ref": run_ref}),
    )
    dispositions = [
        {
            "operation_ref": r["op_ref"],
            "op_id": r["op_id"],
            "batch_id": r["batch_id"],
            "batch_ref": batch_refs[r["batch_id"]],
            "status": "eligible",
        }
        for r in selected_ops
    ]
    run_result = {
        "state": "complete",
        "result_persisted": True,
        "candidates": [{"candidate_ref": candidate_ref, "task_count": len(rows), "status": "completed"}],
        "dispositions": dispositions,
        "operation_effort": {"effort_basis": "runtime_requirement_v1", "items": []},
    }
    conn.execute(
        "INSERT INTO WorkbenchRunReceipts(receipt_ref,run_ref,state,result_json,recorded_at) VALUES (?,?,?,?,?)",
        (format(0xE0000000 + version, "048x"), run_ref, "complete", canonical_json(run_result), adopted_at),
    )
    scheduled_op_ids = [row["op_id"] for row in rows]
    op_type_by_id = {r["op_id"]: r["op_type_id"] for r in op_rows}
    artifact = {
        "status": "completed",
        "sequence": 1,
        "label": "方案 1",
        "algo_mode": "greedy",
        "used_strategy": "due_first",
        "objective_name": "balanced",
        "target_objectives": ["balanced"],
        "generation_policy_version": "unified_search_v1",
        "representative_objectives": ["balanced"],
        "evaluations": {},
        "origin": {"stage": "initial"},
        "first_found_elapsed_ms": 1,
        "search_evidence_ref": "ev-1",
        "task_payload_source": "candidate_tasks_v1",
        "validated_payload": {
            "scheduled_op_ids": scheduled_op_ids,
            "out_of_scope_op_ids": [],
            "validation_errors": [],
        },
        "results": [{"op_id": op_id, "op_type_id": op_type_by_id[op_id]} for op_id in scheduled_op_ids],
        "metrics": {"completion": {"incomplete_batch_ids": []}},
        "summary": {
            "success": True,
            "errors": [],
            "failed_ops": 0,
            "total_ops": len(rows),
            "scheduled_ops": len(rows),
        },
    }
    conn.execute(
        "INSERT INTO WorkbenchRunCandidates(candidate_ref,run_ref,candidate_key,sequence,status,task_count,artifact_json) "
        "VALUES (?,?,?,1,'completed',?,?)",
        (candidate_ref, run_ref, "cand-1", len(rows), canonical_json(artifact)),
    )
    op_ref_by_id = {r["op_id"]: r["op_ref"] for r in op_rows}
    conn.executemany(
        "INSERT INTO WorkbenchRunCandidateTasks(row_ref,candidate_ref,operation_ref,ordinal,payload_json) VALUES (?,?,?,?,?)",
        [
            (
                format((0xF0000000 + version * 100000 + ordinal), "048x"),
                candidate_ref,
                op_ref_by_id[row["op_id"]],
                ordinal,
                canonical_json({
                    "op_id": row["op_id"],
                    "source": "internal",
                    "machine_id": row["machine_id"],
                    "operator_id": row["operator_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "locked": False,
                }),
            )
            for ordinal, row in enumerate(rows)
        ],
    )


def publish_official_plan(conn, version, rows, *, adopted_at=START, operator="local-os-user", record_source=False):
    """Publish an official version as a candidate adoption does: version, audit, rows and receipt.

    ``rows`` are Schedule rows (op_id, machine_id, operator_id, start_time, end_time). Unless
    ``record_source=True`` is requested, the adopted candidate is omitted so readers record the
    legal archived-source gap for it. The caller owns the transaction.
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
    if record_source:
        _record_candidate_adoption_source(
            conn,
            version,
            rows,
            candidate_ref=candidate_ref,
            run_ref=run_ref,
            baseline_ref=baseline_ref,
            previous=previous,
            adopted_at=adopted_at,
            batches=batches,
        )
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
        self.op_id = 0

    def op(self, code="OP1", *, seq=1, piece=None, batch="B1"):
        return self.conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,piece_id,op_type_id,op_type_name,source)
            VALUES (?,?,?,?,'T1','Turning','internal')""", (code, batch, seq, piece)).lastrowid

    def plan(self, version, ids, *, start=START, end=END, record_source=False):
        publish_official_plan(self.conn, version, [{"op_id": op_id, "machine_id": "M1", "operator_id": "O1",
                                                    "start_time": start, "end_time": end} for op_id in ids],
                              record_source=record_source)
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
        with self.ledger.read_snapshot() as scope:
            task = self.ledger.repo.task_headers([task_ref])[task_ref]
            facts = self.ledger.load_many(scope, [task["operation_ref"]], comparison_plan_ref=task["plan_ref"])
            return self.ledger.project_loaded(facts)[0]

    def report_projection(self, report_ref):
        """从所属工序的执行投影里取出这条报工；生产只按工序批量读投影，没有按报工单号单读的入口。"""
        with self.ledger.read_snapshot() as scope:
            header = self.ledger.report_header(report_ref=report_ref)
            assert header is not None
            operation_ref = header["operation_ref"]
            projection = self.ledger.project_operations(scope, [operation_ref])[0]
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
