"""Dedicated real temporary SQLite fixtures. No production application imports."""

import logging
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
from tests._support.sqlite_connection import open_test_connection
from tests.workbench.plan_catalog_support import ensure_history_head, insert_schedule_rows

NOW = datetime(2026, 9, 10, 12)
START, END = "2026-09-09T08:00:00", "2026-09-09T10:00:00"
PLAN_INTENT = {"reason": "台账夹具正式计划", "declared_operator": "fixture-operator"}


def current_database(path):
    """A fixture database built exactly as production creates a new one."""
    ensure_schema(str(path), logging.getLogger(__name__), schema_path=str(REPO_ROOT / "schema.sql"))
    return open_test_connection(path)


def official_plan_ref(conn, version):
    return conn.execute("SELECT plan_ref FROM ScheduleHistory WHERE version=?", (version,)).fetchone()[0]


def _source_candidate(rows, op_by_id, *, candidate_ref, run_ref, version, batch_count):
    """The adopted source as the run writer stores a candidate: one unified-search plan arranged exactly as
    ``rows``, its validated payload and task rows, and the artifact built from the production key table."""
    from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
    from core.algorithms.evaluation import ScheduleMetrics
    from core.algorithms.evaluation_completion import BatchCompletion
    from core.models.enums import SortStrategy
    from core.models.workbench_run_job import durable_value
    from core.services.scheduler.run.schedule_candidate_plan import CandidatePlan
    from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
    from core.services.workbench.facts.candidate_artifact import (
        ARTIFACT_FIELDS,
        metrics_record,
        result_traces,
        summary_record,
        validated_payload_record,
    )

    results = []
    for row in rows:
        op = op_by_id[row["op_id"]]
        results.append(ScheduleResult(
            op_id=op["op_id"], op_code=op["op_code"], batch_id=op["batch_id"], seq=op["seq"],
            machine_id=row["machine_id"], operator_id=row["operator_id"],
            start_time=datetime.fromisoformat(row["start_time"]), end_time=datetime.fromisoformat(row["end_time"]),
            op_type_name=op["op_type_name"], op_type_id=op["op_type_id"],
        ))
    completion = BatchCompletion(
        expected_operation_count=len(results), missing_operation_count=0, unexpected_result_count=0,
        complete_batch_count=batch_count, incomplete_batch_ids=(), partial_batch_ids=(),
        failure_detail_count=0, failure_batch_ids=(),
    )
    plan = CandidatePlan(
        sequence=1, candidate_key="cand-1", label="方案 1", score=(0.0,),
        summary=ScheduleSummary(success=True, total_ops=len(results), scheduled_ops=len(results), failed_ops=0,
                                warnings=[], errors=[], duration_seconds=0.0),
        metrics=ScheduleMetrics(overdue_count=0, total_tardiness_hours=0.0, makespan_hours=0.0, changeover_count=0,
                                completion=completion),
        origin={"stage": "initial"}, first_found_elapsed_ms=1,
        search_evidence_ref={"source_event_id": None, "run_ref": run_ref}, used_params={}, results=results,
        used_strategy=SortStrategy.DUE_DATE_FIRST, algo_mode="greedy",
        objective_name="balanced", representative_objectives=["balanced"],
    )
    # 夹具安排都有正时长，没有零工时见证可核。
    payload = build_validated_schedule_payload(
        results, operations=[], operation_sources={row.op_id: row.source for row in results},
        allowed_op_ids={row.op_id for row in results}, missing_internal_resource_op_ids=set(),
        point_validator=lambda row: None,
    )
    records = {"sort_strategy": plan.used_strategy.value, "target_objectives": ["balanced"],
               "summary": summary_record(plan.summary),
               "metrics": metrics_record(plan.metrics), "results": result_traces(plan.results),
               "validated_payload": validated_payload_record(payload)}
    return {
        "candidate_ref": candidate_ref,
        "key": plan.candidate_key,
        "sequence": plan.sequence,
        "artifact": {name: records[name] if name in records else durable_value(getattr(plan, name))
                     for name in ARTIFACT_FIELDS},
        "tasks": [
            {
                "row_ref": format((0xF0000000 + version * 100000 + ordinal), "048x"),
                "operation_ref": op_by_id[row.op_id]["op_ref"],
                "op_id": row.op_id,
                "source": row.source,
                "machine_id": row.machine_id,
                "operator_id": row.operator_id,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "locked": False,
            }
            for ordinal, row in enumerate(payload.schedule_rows)
        ],
    }


def _record_candidate_adoption_source(conn, version, rows, *, candidate_ref, run_ref, baseline_ref, previous, adopted_at, batches):
    from core.models.workbench_preflight import normalize_preflight_input
    from core.services.workbench.facts.candidate_facts import GenerationFacts, build_run_archive_rows
    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from data.repositories.workbench_run_repo import WorkbenchRunRepository
    from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository, encode_candidate_rows

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
            "SELECT bo.id AS op_id, bo.op_code, bo.batch_id, bo.seq, bo.op_type_id, bo.op_type_name, s.ref AS op_ref "
            "FROM BatchOperations bo JOIN WorkbenchPlanSourceRefs s "
            "ON s.kind='operation' AND s.active=1 AND CAST(bo.id AS TEXT)=s.source_key"
        )
    )
    selected_ops = [r for r in op_rows if r["batch_id"] in batches]
    exec_op_refs = sorted({r["op_ref"] for r in op_rows if r["batch_id"] in batches or r["op_id"] in prev_op_ids})
    ledger_svc = ExecutionLedgerService(conn)
    with ledger_svc.read_snapshot() as scope:
        projections = [
            item
            for start_idx in range(0, len(exec_op_refs), 5000)
            for item in ledger_svc.project_operations(scope, exec_op_refs[start_idx : start_idx + 5000])
        ]
    capture = ProductionFactsCapture(conn)
    revisions = capture.revisions_record()
    busy_refs = [item.operation_ref for item in projections if item.execution_state in ("partial", "started")]
    scoped_facts = capture.scoped_archive(
        sorted(batch_refs.values()),
        baseline_version=previous,
        busy_operation_refs=busy_refs,
    )
    revisions_json = canonical_json(revisions)
    conditions_archive_json = canonical_json(scoped_facts)
    facts = GenerationFacts({
        "run_ref": run_ref,
        "input": settings,
        "revisions": revisions,
        "facts": scoped_facts,
        "execution": [item.to_dict() for item in projections],
        "baseline": baseline,
    })
    archive_batches, archive_operations = build_run_archive_rows(run_ref, facts)
    run_repo = WorkbenchRunRepository(conn)
    run_repo.insert(
        request_key=run_request_key,
        input_ref=input_ref,
        settings=settings,
        revisions_json=revisions_json,
        conditions_archive_json=conditions_archive_json,
        projections=projections,
        baseline=baseline,
        now=adopted_at,
        run_ref=run_ref,
        batches=archive_batches,
        operations=archive_operations,
    )
    run_repo.claim(run_ref, format(0x90000000 + version, "048x"), adopted_at)
    conn.execute(
        "UPDATE WorkbenchRunJobs SET state='complete', stage='finished', finished_at=? WHERE run_ref=?",
        (adopted_at, run_ref),
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
        "candidates": [{"candidate_ref": candidate_ref, "task_count": len(rows)}],
        "dispositions": dispositions,
        "operation_effort": {"effort_basis": "runtime_requirement_v1", "items": []},
    }
    conn.execute(
        "INSERT INTO WorkbenchRunReceipts(receipt_ref,run_ref,state,result_json,recorded_at) VALUES (?,?,?,?,?)",
        (format(0xE0000000 + version, "048x"), run_ref, "complete", canonical_json(run_result), adopted_at),
    )
    op_by_id = {r["op_id"]: r for r in op_rows}
    source = _source_candidate(rows, op_by_id, candidate_ref=candidate_ref, run_ref=run_ref, version=version,
                               batch_count=len(batches))
    WorkbenchRunResultRepository(conn).save(run_ref, encode_candidate_rows([source]))


def publish_official_plan(conn, version, rows, *, adopted_at=START, operator="local-os-user", record_source=False):
    """Publish an official version as a candidate adoption does: version, header, rows and receipt.

    ``rows`` are Schedule rows (op_id, machine_id, operator_id, start_time, end_time). Unless
    ``record_source=True`` is requested, the adopted candidate is omitted so readers record the
    legal archived-source gap for it. The caller owns the transaction.
    """
    candidate_ref, run_ref = format(0xC0000000 + version, "048x"), format(0xA0000000 + version, "048x")
    request_key = "fixture-plan-adopt-" + format(version, "04d")
    previous = conn.execute("SELECT max(version) FROM ScheduleHistory WHERE version<?", (version,)).fetchone()[0]
    baseline_ref = official_plan_ref(conn, previous) if previous is not None else None
    baseline_task_count = (
        conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=?", (previous,)).fetchone()[0]
        if previous is not None
        else 0
    )
    times = [row[key] for row in rows for key in ("start_time", "end_time")]
    material_policy = {
        "ready_check": True,
        "material_strategy": "strict",
        "start_date": min(times)[:10],
        "end_date": max(times)[:10],
    }
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
    plan_ref = ensure_history_head(
        conn,
        version,
        strategy="manual",
        schedule_time=adopted_at,
        adopted_at=adopted_at,
        created_by=operator,
        request_key=request_key,
        declared_operator=PLAN_INTENT["declared_operator"],
        application_operator=operator,
        reason=PLAN_INTENT["reason"],
        source_kind="candidate_adoption",
        source_ref=candidate_ref,
        source_label="方案 1",
        run_ref=run_ref,
        accepted_at=adopted_at,
        finished_at=adopted_at,
        baseline_version=previous,
        baseline_ref=baseline_ref,
        baseline_kind="admission_official",
        baseline_captured_at=adopted_at,
        baseline_captured_task_count=baseline_task_count,
        material_policy=material_policy,
        deferred_operation_ids=[],
        operation_effort={"effort_basis": "runtime_requirement_v1", "items": []} if record_source else None,
    )
    schedule_items = (
        rows
        if record_source
        else [{**row, "op_type_ref": None, "op_type_label": None} for row in rows]
    )
    insert_schedule_rows(conn, version, schedule_items, sync_history=True)
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
        self.ledger = ExecutionLedgerService(conn)
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
        return self.conn.execute(
            "SELECT task_ref FROM Schedule WHERE version=? AND op_id=?",
            (version, op_id),
        ).fetchone()[0]

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
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Lathe')")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
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
