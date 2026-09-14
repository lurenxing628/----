"""Read-only piece proof shared by computation, candidate and trial adoption.

Call inside the caller's adoption snapshot and repeat in its write transaction.
The caller still owns saved-source/raw equality, candidate/scenario identity,
baseline admission, request receipts and append-only official persistence.
This replaces the batch-only constraints/execution check for a piece scope; do
not also run the legacy flat-seq downstream check over independent pieces.
"""

from dataclasses import asdict
from datetime import datetime, timedelta

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.errors import AppError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked, PieceAdoptionEvidence
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.resource_pool_builder import load_machine_downtimes
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.scheduler.schedule_service import ScheduleService

from .messages import FAILURE
from .piece_adoption_execution import validate_piece_execution
from .piece_adoption_facts import current_piece_scope
from .piece_adoption_scope import block
from .preflight_checks import PreflightChecks, stored_date
from .run_candidate_adoption_constraints import _TABLES, _resource_overlaps
from .run_input_external import prime_template_cache
from .run_input_readonly import candidate_read_snapshot
from .run_input_runtime import _validate_stored_runtime
from .zero_duration import PointEventError, candidate_point_validator, estimate_point_event, internal_duration_hours


def validate_piece_adoption(conn, *, prepared, payload):
    """Return PieceAdoptionEvidence; raise a typed blocker without writes or repair.

    prepared uses the existing CandidateRunInput fields, including raw operations,
    dispositions with complete ExecutionProjection.to_dict(), original batches,
    calendar, seeds and full execution guards. payload is ValidatedSchedulePayload.
    No proof is inferred from the engine's completion flag.
    """
    try:
        return _validate_piece_adoption(conn, prepared, payload)
    except PieceAdoptionBlocked:
        raise
    except (CandidateAdoptionBlocked, CandidateRunInputError, PointEventError) as exc:
        raise PieceAdoptionBlocked(exc.code, str(exc)) from exc
    except AppError as exc:
        code = (exc.details or {}).get("reason", "piece_constraint_unproven")
        raise PieceAdoptionBlocked(code, str(exc)) from exc
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise PieceAdoptionBlocked("piece_evidence_incomplete", "分件排产依据不完整或有错，本次没有采用。请回「执行排产」重新排一次。") from exc


def _validate_piece_adoption(conn, prepared, payload):
    with candidate_read_snapshot(conn):
        if prepared.cal_svc.conn is not conn:
            block("piece_connection_mismatch", FAILURE)
        scope, refs = current_piece_scope(conn, prepared)
        _payload(prepared, payload, scope)
        svc = ScheduleService(conn)
        protected = validate_piece_execution(svc, prepared, payload, scope, refs)
        prime_template_cache(svc, _template_tables(conn), prepared.batches, prepared.operations)
        algo_ops = {op.id: op for op in build_algo_operations(svc, prepared.operations, strict_mode=True)}
        _precedence(payload, scope, algo_ops)
        _constraints(conn, prepared, payload, scope, algo_ops)
        return PieceAdoptionEvidence(scope, tuple(sorted(refs.items())), tuple(sorted(protected)),
                                     prepared.execution_snapshot_revision)


def _template_tables(conn):
    return {name: [dict(row) for row in conn.execute('SELECT * FROM "' + name + '"')]
            for name in ("PartOperations", "ExternalGroups")}


def _payload(prepared, payload, scope):
    ids = {work.op_id for work in scope.operations}
    if (prepared.schedule_output_allowed_op_ids != ids or payload.scheduled_op_ids != ids
            or len(payload.schedule_rows) != len(ids)):
        block("piece_scope_incomplete", "排产结果没有把共同工序和每个分件各排一次，本次没有采用。请回「执行排产」重新排一次。")
    for row in payload.schedule_rows:
        for time in (row.start_time, row.end_time):
            if not isinstance(time, datetime) or time.tzinfo is not None or time.microsecond:
                block("piece_time_unrepresentable", "排产结果的开始或结束时刻不是整秒，写不进正式计划。请回「执行排产」重新排一次。")
    checked = build_validated_schedule_payload(list(payload.schedule_rows), allowed_op_ids=ids,
        operations=prepared.operations, point_validator=candidate_point_validator(prepared))
    if checked != payload:
        block("piece_payload_inconsistent", "排产结果的工序行、设备人员分配和工序编号对不上，本次没有采用。请回「执行排产」重新排一次。")


def _precedence(payload, scope, ops):
    rows = {row.op_id: row for row in payload.schedule_rows}
    for work in scope.operations:
        row = rows[work.op_id]
        for predecessor in work.predecessor_op_ids:
            previous, left, right = rows[predecessor], ops[predecessor], ops[work.op_id]
            merged = (left.source == right.source == "external" and left.piece_id == right.piece_id
                      and left.ext_merge_mode == right.ext_merge_mode == "merged"
                      and left.ext_group_id == right.ext_group_id and left.ext_group_id is not None)
            if merged:
                if (previous.start_time, previous.end_time) != (row.start_time, row.end_time):
                    block("piece_merged_group_split", "同一个合并外协组里的工序时间不一致，本次没有采用。请回「执行排产」重新排一次。")
            elif row.start_time < previous.end_time:
                block("piece_precedence_violation", "有后道工序早于本分件或共同工序的前道工序开始，本次没有采用。请回「执行排产」重新排一次。")


def _constraints(conn, prepared, payload, scope, algo_ops):
    _validate_stored_runtime(conn)
    calendar = CalendarService(conn)
    downtime = load_machine_downtimes(ScheduleService(conn),
        algo_ops=list(payload.schedule_rows),
        start_dt=min(row.start_time for row in payload.schedule_rows))
    checks = PreflightChecks({name: [dict(row) for row in conn.execute('SELECT * FROM "' + name + '"')]
                              for name in _TABLES})
    quantities = {work.op_id: work.target_quantity for work in scope.operations}
    ops = {op.id: op for op in prepared.operations}
    actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    seeds = {row["op_id"] for row in prepared.seed_results}
    high = datetime.combine(prepared.end_date_norm + timedelta(days=1), datetime.min.time())
    _resource_overlaps(payload.schedule_rows)
    for row in payload.schedule_rows:
        op, algo = ops[row.op_id], algo_ops[row.op_id]
        batch = prepared.batches[op.batch_id]
        raw = dict(asdict(op), machine_id=row.machine_id, operator_id=row.operator_id)
        if checks.fields(asdict(batch), raw) or checks.resources(raw):
            block("piece_resource_invalid", "原工序资料或分配的设备、人员、工种资格有问题，本次没有采用。请到基础资料核对后重新排产。")
        if row.op_id in actual:
            continue
        _mutable_work(prepared, checks, row, op, batch, quantities[row.op_id], seeds, high)
        _duration(calendar, downtime, row, algo, batch, quantities[row.op_id])


def _mutable_work(prepared, checks, row, op, batch, quantity, seeds, high):
    if op.status in ("processing", "completed", "skipped") or batch.status in ("completed", "cancelled"):
        block("piece_execution_unprotected", "已开工、已完工或已取消的工序没有对应的报工记录保护，本次没有采用。请刷新现场记录后重新排产。")
    if op.source == "external" and quantity == 0:
        block("piece_scope_incomplete", "外协工序的目标数量是 0，排不出工期，本次没有采用。请到批次管理补数量后重新排产。")
    if row.op_id not in seeds and (row.start_time < prepared.start_dt_norm or row.end_time > high
                                  or row.start_time == high):
        block("piece_outside_window", "有工序排到了这次排产日期范围之外，本次没有采用。请回「执行排产」重新排一次。")
    if checks.readiness(asdict(batch), prepared.readiness_gate_enabled):
        block("piece_material_not_ready", "批次齐套条件不满足，本次没有采用。请到批次管理核对齐套状态后重新排产。")
    if batch.ready_date is not None:
        ready = stored_date(batch.ready_date)
        if ready is None:
            block("piece_ready_date_invalid", "原齐套日期格式不对，本次没有采用。请到批次管理核对后重新排产。")
        if row.start_time < datetime.fromisoformat(ready):
            block("piece_before_ready_date", "有工序排在齐套日期之前，本次没有采用。请回「执行排产」重新排一次。")


def _duration(calendar, downtime, row, op, batch, quantity):
    if op.source == "external":
        days = op.ext_group_total_days if op.ext_merge_mode == "merged" else op.ext_days
        if (row.machine_id is not None or row.operator_id is not None
                or calendar.add_calendar_days(row.start_time, days) != row.end_time):
            block("piece_external_duration_conflict", "外协工序的周期或设备人员安排和原资料不一致，本次没有采用。请回「执行排产」重新排一次。")
        return
    total = internal_duration_hours(op.setup_hours, op.unit_hours, quantity)
    if row.start_time == row.end_time:
        start, end = estimate_point_event(calendar, setup_hours=op.setup_hours, unit_hours=op.unit_hours,
            quantity=quantity, machine_id=row.machine_id, operator_id=row.operator_id,
            priority=batch.priority, start=row.start_time)
        if (start, end) != (row.start_time, row.end_time):
            block("piece_calendar_duration_conflict", "零工时工序的时刻和当前工作日历算出来的不一致，本次没有采用。请回「执行排产」重新排一次。")
        return
    slot = estimate_internal_slot(calendar=calendar, op=op, batch=batch,
        machine_id=row.machine_id, operator_id=row.operator_id, base_time=row.start_time,
        prev_end=row.start_time, machine_timeline=(), operator_timeline=(), end_dt_exclusive=None,
        machine_downtimes=downtime.get(row.machine_id, ()),
        last_op_type_by_machine=None, abort_after=None, total_hours_base=total)
    if (slot.efficiency_fallback_used or slot.start_time != row.start_time or slot.end_time != row.end_time):
        block("piece_calendar_duration_conflict", "工序时长和数量、工时定额、工作日历算出来的对不上，本次没有采用。请回「执行排产」重新排一次。")
