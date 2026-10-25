"""Read-only piece proof shared by candidate publication and formal adoption.

Publication accepts a closed partial scope; adoption requires the whole scope.
Adoption repeats its proof in the caller's write transaction.
The caller still owns saved-source/raw equality, candidate/scenario identity,
baseline admission, request receipts and append-only official persistence.
This replaces the batch-only constraints/execution check for a piece scope; do
not also run the legacy flat-seq downstream check over independent pieces.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta

from core.errors import AppError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.run.schedule_input_seed_metadata import MERGED_EXECUTION_GROUP_SOURCE
from core.services.workbench.facts.piece_scope import block
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.zero_duration import PointEventError

from .candidate_adoption_constraints import (
    _resource_overlaps,
    adoption_downtimes,
    adoption_external_intervals,
    calendar_duration_conflict,
    external_duration_conflict,
    external_holds_resources,
)
from .piece_adoption_execution import _quantities, validate_piece_execution
from .piece_adoption_facts import current_piece_scope


def validate_piece_candidate(conn, *, prepared, payload, context=None, candidate_validated=False):
    """Validate a known payload for publication while retaining every protected seed."""
    return _validate_piece(
        conn, prepared, payload, purpose="publication", context=context, candidate_validated=candidate_validated
    )


def validate_piece_adoption(conn, *, prepared, payload, candidate_validated=False):
    """Validate formal adoption for a piece scope; raise a typed blocker without writes or repair.

    prepared uses the existing CandidateRunInput fields, including raw operations,
    dispositions with complete ExecutionProjection.to_dict(), original batches,
    calendar, seeds and full execution guards. payload is ValidatedSchedulePayload.
    No proof is inferred from the engine's completion flag.
    """
    return _validate_piece(conn, prepared, payload, purpose="adoption", candidate_validated=candidate_validated)


@contextmanager
def _piece_validation_snapshot(conn):
    try:
        with candidate_read_snapshot(conn):
            yield
    except PieceAdoptionBlocked:
        raise
    except (CandidateAdoptionBlocked, CandidateRunInputError, PointEventError) as exc:
        raise PieceAdoptionBlocked(exc.code, str(exc)) from exc
    except AppError as exc:
        code = (exc.details or {}).get("reason", "piece_constraint_unproven")
        raise PieceAdoptionBlocked(code, str(exc)) from exc


def prepare_piece_validation_context(conn, prepared):
    """Prepare shared proof inside the current snapshot, never across requests."""
    with _piece_validation_snapshot(conn):
        return _prepare_piece_validation_context(conn, prepared)


def _prepare_piece_validation_context(conn, prepared):
    scope, refs = current_piece_scope(conn, prepared)
    _quantities(scope, refs, prepared.preflight_facts.execution_projections)
    algo_ops = {op.id: op for op in prepared.algo_ops}
    ops = {op.id: op for op in prepared.operations}
    raw_batches = {batch_id: vars(batch) for batch_id, batch in prepared.batches.items()}
    checks = prepared.preflight_facts.checks()
    actual_intervals = adoption_external_intervals(prepared, algo_ops=algo_ops.values())
    derived = {seed["op_id"] for seed in prepared.seed_results if seed.get("seed_source") == MERGED_EXECUTION_GROUP_SOURCE}
    if not derived <= set(actual_intervals):
        block("piece_execution_protection_changed", "同组固定安排缺少对应的实际外协周期依据，本次没有采用。请刷新后重新排产。")
    _material_deferrals(prepared, checks, ops, raw_batches)
    return {
        "scope": scope,
        "algo_ops": algo_ops,
        "ops": ops,
        "raw_batches": raw_batches,
        "checks": checks,
        "quantities": {work.op_id: work.target_quantity for work in scope.operations},
        "actual_intervals": actual_intervals,
        "downtime": adoption_downtimes(prepared),
        "actual": prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids,
        "seeds": {row["op_id"] for row in prepared.seed_results},
        "high": datetime.combine(prepared.end_date_norm + timedelta(days=1), datetime.min.time()),
    }


def _validate_piece(conn, prepared, payload, *, purpose, context=None, candidate_validated):
    with _piece_validation_snapshot(conn):
        if context is None:
            context = _prepare_piece_validation_context(conn, prepared)
        scope = context["scope"]
        _payload(prepared, payload, scope, purpose=purpose, candidate_validated=candidate_validated)
        validate_piece_execution(prepared, payload, purpose=purpose)
        _constraints(prepared, payload, context, candidate_validated=candidate_validated)


def _payload(prepared, payload, scope, *, purpose, candidate_validated):
    scope_ids = {work.op_id for work in scope.operations}
    ids = scope_ids - {row["op_id"] for row in prepared.dispositions if row["status"] == "skipped"}
    adoption_ids = scope_ids - material_deferred_ids(prepared.dispositions, prepared.normalized_input)
    scheduled = {row.op_id for row in payload.schedule_rows}
    if (prepared.schedule_output_allowed_op_ids != ids or payload.scheduled_op_ids != scheduled
            or len(payload.schedule_rows) != len(scheduled) or not scheduled <= ids
            or (purpose == "publication" and not scheduled)
            or (purpose == "adoption" and scheduled != adoption_ids)):
        block("piece_scope_incomplete", "排产结果没有把共同工序和每个分件各排一次，本次没有采用。请回「执行排产」重新排一次。")
    if not candidate_validated:
        for row in payload.schedule_rows:
            for time in (row.start_time, row.end_time):
                if not isinstance(time, datetime) or time.tzinfo is not None:
                    block("piece_time_unrepresentable", "排产结果的开始或结束时刻无效，写不进正式计划。请回「执行排产」重新排一次。")


def _constraints(prepared, payload, context, *, candidate_validated):
    calendar, checks = prepared.cal_svc, context["checks"]
    downtime, actual_intervals = context["downtime"], context["actual_intervals"]
    quantities, ops, algo_ops = context["quantities"], context["ops"], context["algo_ops"]
    raw_batches = context["raw_batches"]
    actual, seeds, high = context["actual"], context["seeds"], context["high"]
    _resource_overlaps(payload.schedule_rows, prepared.execution_facts)
    for row in payload.schedule_rows:
        op, algo = ops[row.op_id], algo_ops[row.op_id]
        batch, raw_batch = prepared.batches[op.batch_id], raw_batches[op.batch_id]
        raw = {**vars(op), "machine_id": row.machine_id, "operator_id": row.operator_id}
        protected_cycle = row.op_id in actual or row.op_id in actual_intervals
        resource_issues = checks.protected_resources(raw) if protected_cycle else checks.fields(raw_batch, raw) + checks.resources(raw)
        if resource_issues:
            block("piece_resource_invalid", "原工序资料或分配的设备、人员、工种资格有问题，本次没有采用。请到基础资料核对后重新排产。")
        if row.op_id in actual:
            continue
        _mutable_work(prepared, checks, row, op, batch, raw_batch, raw, quantities[row.op_id], seeds, high,
                      actual_cycle=row.op_id in actual_intervals, candidate_validated=candidate_validated)
        _duration(
            calendar, downtime, row, algo, batch, quantities[row.op_id], actual_intervals,
            candidate_validated=candidate_validated,
        )


def _material_deferrals(prepared, checks, ops, raw_batches):
    deferred = material_deferred_ids(prepared.dispositions, prepared.normalized_input)
    current = []
    for op_id in deferred:
        op = ops[op_id]
        batch, raw = raw_batches[op.batch_id], vars(op)
        if checks.fields(batch, raw):
            block("piece_resource_invalid", "待料工序的原始资料不完整，请核对后重新排产。")
        problems, _day = checks.operation_readiness(batch, raw, prepared.normalized_input)
        current.append({"op_id": op_id, "status": "skipped", "issues": problems})
    if material_deferred_ids(current, prepared.normalized_input) != deferred:
        block("piece_scope_incomplete", "被暂缓的工序没有当前缺料依据，请重新排产。")


def _mutable_work(prepared, checks, row, op, batch, raw_batch, raw, quantity, seeds, high, *,
                  actual_cycle, candidate_validated):
    if op.status in ("processing", "completed", "skipped") or batch.status in ("completed", "cancelled"):
        block("piece_execution_unprotected", "已开工、已完工或已取消的工序没有对应的报工记录保护，本次没有采用。请刷新现场记录后重新排产。")
    if op.source == "external" and quantity == 0:
        block("piece_scope_incomplete", "外协工序的目标数量是 0，排不出工期，本次没有采用。请到批次管理补数量后重新排产。")
    if not candidate_validated and row.op_id not in seeds and (
        row.start_time < prepared.start_dt_norm or row.end_time > high or row.start_time == high
    ):
        block("piece_outside_window", "有工序排到了这次排产日期范围之外，本次没有采用。请回「执行排产」重新排一次。")
    if not actual_cycle:
        _release_dates(prepared, checks, row, batch, raw_batch, raw)


def _release_dates(prepared, checks, row, batch, raw_batch, raw):
    material_issues, material_day = checks.operation_readiness(raw_batch, raw, prepared.normalized_input)
    if material_issues:
        block("piece_material_not_ready", "批次齐套条件不满足，本次没有采用。请到批次管理核对齐套状态后重新排产。")
    if material_day and row.start_time < datetime.fromisoformat(material_day):
        block("piece_before_material", "有工序早于本序物料到齐日期，本次没有采用。请重新排产。")
    if prepared.normalized_input["ready_check"] and batch.ready_date is not None:
        ready = stored_date(batch.ready_date)
        if ready is None:
            block("piece_ready_date_invalid", "原齐套日期格式不对，本次没有采用。请到批次管理核对后重新排产。")
        if row.start_time < datetime.fromisoformat(ready):
            block("piece_before_ready_date", "有工序排在齐套日期之前，本次没有采用。请回「执行排产」重新排一次。")


def _duration(calendar, downtime, row, op, batch, quantity, actual_intervals, *, candidate_validated):
    if op.source == "external":
        if (external_holds_resources(row)
                or external_duration_conflict(calendar, row, op, actual_intervals)):
            block("piece_external_duration_conflict", "外协工序的周期或设备人员安排和原资料不一致，本次没有采用。请回「执行排产」重新排一次。")
        return
    if candidate_validated and row.start_time == row.end_time:
        return
    if calendar_duration_conflict(calendar, row, op, batch, downtime.get(row.machine_id, ()), quantity=quantity):
        if row.start_time == row.end_time:
            block("piece_calendar_duration_conflict", "零工时工序的时刻和当前工作日历算出来的不一致，本次没有采用。请回「执行排产」重新排一次。")
        block("piece_calendar_duration_conflict", "工序时长和数量、工时定额、工作日历算出来的对不上，本次没有采用。请回「执行排产」重新排一次。")
