"""Prove resources, occupied intervals, calendar duration and readiness explicitly."""

from collections import defaultdict
from datetime import datetime

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.scheduler.execution.execution_ledger_guard import fact_resource_segments
from core.services.scheduler.run.schedule_execution_reservations import reserve_execution_machines
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_actual_group_intervals,
    merged_external_group_identity,
)
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.zero_duration import (
    estimate_point_event,
    internal_duration_hours,
)

from .input_runtime import runtime_resource_facts


def _block(code, message):
    raise CandidateAdoptionBlocked(code, message)


def _resource_overlaps(rows, execution_facts):
    timelines = defaultdict(list)
    for row in rows:
        if row.source == "internal" and row.start_time < row.end_time:
            fact = execution_facts.get(row.op_id)
            segments = fact_resource_segments(fact) if fact is not None else ()
            if not segments:
                segments = ((row.start_time, row.end_time, row.machine_id, row.operator_id),)
            for start, end, machine, operator in segments:
                timelines["machine_id", machine].append((start, end, row.op_id))
                timelines["operator_id", operator].append((start, end, row.op_id))
    for intervals in timelines.values():
        previous_end = None
        for start, end, _ in sorted(intervals):
            if previous_end is not None and start < previous_end:
                _block("candidate_resource_overlap", "候选内设备或人员安排重叠，不能正式采用。")
            previous_end = end


def adoption_downtimes(prepared, payload=None):
    if payload is not None:
        actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
        rows = [row for row in payload.schedule_rows if row.source == "internal" and row.op_id not in actual]
        if not rows:
            return {}
    # Locked seeds may precede the requested run window. Prove every planned
    # arrangement against downtime at its own time and assigned machine.
    downtimes = runtime_resource_facts(prepared.preflight_facts).downtimes
    return reserve_execution_machines(downtimes, prepared.execution_reservations)


def calendar_duration_conflict(calendar, row, op, batch, machine_downtimes, *, quantity):
    """按真实班次、效率、停机和工时从安排的开工时刻重算一遍；开完工对不上（或效率要兜底）即冲突。"""
    if row.start_time == row.end_time:
        start, end = estimate_point_event(calendar, setup_hours=op.setup_hours, unit_hours=op.unit_hours,
            quantity=quantity, machine_id=row.machine_id, operator_id=row.operator_id,
            priority=batch.priority, start=row.start_time)
        return (start, end) != (row.start_time, row.end_time)
    total = internal_duration_hours(op.setup_hours, op.unit_hours, quantity)
    estimate = estimate_internal_slot(calendar=calendar, op=op, batch=batch,
        machine_id=row.machine_id, operator_id=row.operator_id, base_time=row.start_time,
        prev_end=row.start_time, machine_timeline=(), operator_timeline=(), end_dt_exclusive=None,
        machine_downtimes=machine_downtimes,
        last_op_type_by_machine=None, abort_after=None, total_hours_base=total)
    return (estimate.efficiency_fallback_used or estimate.start_time != row.start_time
            or estimate.end_time != row.end_time)


def _internal(prepared, row, op, batch, downtime):
    if row.start_time == row.end_time:
        # validate_candidate 已按同一份 prepared 核对点事件。
        return
    if calendar_duration_conflict(prepared.cal_svc, row, op, batch, downtime.get(row.machine_id, ()),
                                  quantity=batch.quantity):
        _block("candidate_calendar_duration_conflict", "候选开完工时间与真实班次、效率、停机或工时不一致。")


def adoption_external_intervals(prepared, *, algo_ops=None):
    groups = {op.id: merged_external_group_identity(op) for op in (prepared.algo_ops if algo_ops is None else algo_ops)}
    actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    cycles = merged_actual_group_intervals(groups, prepared.execution_seed_results, actual)
    return {op_id: cycles[identity] for op_id, identity in groups.items() if identity in cycles}


def external_holds_resources(row):
    """外协安排不能占本厂设备人员。"""
    return row.machine_id is not None or row.operator_id is not None


def external_duration_conflict(calendar, row, op, actual_intervals):
    expected = actual_intervals.get(row.op_id)
    if expected is None:
        days = op.ext_group_total_days if op.ext_merge_mode == "merged" else op.ext_days
        expected = row.start_time, calendar.add_calendar_days(row.start_time, days)
    return expected != (row.start_time, row.end_time)


def _external(prepared, row, op, actual_intervals):
    if external_holds_resources(row):
        _block("candidate_external_resource_conflict", "外协候选带有未支持的内部资源占用。")
    if external_duration_conflict(prepared.cal_svc, row, op, actual_intervals):
        _block("candidate_external_duration_conflict", "外协候选与真实外协周期不一致。")


_ARRANGEMENT_MESSAGES = {
    "candidate_resource_invalid": "候选实际使用的设备、人员资质、工种或供应商不合法。",
    "candidate_material_not_ready": "候选仍有未齐套物料，不能正式采用。",
    "candidate_before_material": "候选安排早于本工序物料到齐日期。",
    "candidate_before_ready_date": "候选安排早于实际可开工日期。",
}


def arrangement_problem(checks, batch, raw, start_time, settings):
    """一条非实际安排按现在的资料还成不成立：工序资料和设备人员资格、物料到齐日、齐套日期。

    batch、raw 是原始行，raw 的设备人员换成安排行自己的。返回第一处不成立的原因码，都成立返回 None。
    候选采用逐行复核与排产检查核对不重排时段保留的原安排共用这一口径。
    """
    if checks.fields(batch, raw) or checks.resources(raw):
        return "candidate_resource_invalid"
    material_issues, material_day = checks.operation_readiness(batch, raw, settings)
    if material_issues:
        return "candidate_material_not_ready"
    # SQLite DECLTYPES returns date objects in the application; snapshots use ISO text.
    # batch_model has already rejected invalid dates using the same parser.
    if material_day and start_time < datetime.fromisoformat(material_day):
        return "candidate_before_material"
    ready_day = stored_date(batch["ready_date"])
    if settings["ready_check"] and ready_day is not None and start_time < datetime.fromisoformat(ready_day):
        return "candidate_before_ready_date"
    return None


def _protected_arrangement(prepared, checks, row, raw, algo, actual_ids, actual_intervals):
    if row.op_id not in actual_ids and row.op_id not in actual_intervals:
        return False
    if checks.protected_resources(raw):
        _block("candidate_resource_invalid", "实际安排的原资源身份或自制外协归属不完整，不能正式采用。")
    if row.op_id not in actual_ids:
        _external(prepared, row, algo, actual_intervals)
    return True


def validate_adoption_constraints(prepared, payload):
    checks = prepared.preflight_facts.checks()
    ops = {op.id: op for op in prepared.operations}
    raw_batches = {batch_id: vars(batch) for batch_id, batch in prepared.batches.items()}
    algo_ops = {op.id: op for op in prepared.algo_ops}
    actual_ids = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    downtime = adoption_downtimes(prepared, payload)
    actual_intervals = adoption_external_intervals(prepared)
    _resource_overlaps(payload.schedule_rows, prepared.execution_facts)
    for row in payload.schedule_rows:
        op, batch = ops[row.op_id], prepared.batches[ops[row.op_id].batch_id]
        raw = {**vars(op), "machine_id": row.machine_id, "operator_id": row.operator_id}
        # Actual production is a fact, not a duration that may be recomputed.
        # validate_candidate + execution guard retain its exact seed and identity.
        if _protected_arrangement(prepared, checks, row, raw, algo_ops[row.op_id], actual_ids, actual_intervals):
            continue
        code = arrangement_problem(checks, raw_batches[op.batch_id], raw, row.start_time, prepared.normalized_input)
        if code is not None:
            _block(code, _ARRANGEMENT_MESSAGES[code])
        if row.source == "internal":
            _internal(prepared, row, algo_ops[row.op_id], batch, downtime)
        else:
            _external(prepared, row, algo_ops[row.op_id], actual_intervals)
