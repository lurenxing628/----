"""Prove resources, occupied intervals, calendar duration and readiness explicitly."""

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.scheduler.resource_pool_builder import load_machine_downtimes
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_actual_group_intervals,
    merged_external_group_identity,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.facts.preflight_checks import PreflightChecks, stored_date
from core.services.workbench.facts.zero_duration import candidate_point_validator
from data.repositories.workbench_run_input_repo import ADOPTION_CHECK_TABLES, WorkbenchRunInputRepository

# piece_adoption 仍按这份表清单读主数据；清单本体归输入仓储维护。
_TABLES = ADOPTION_CHECK_TABLES


def _block(code, message):
    raise CandidateAdoptionBlocked(code, message)


def _resource_overlaps(rows):
    timelines = defaultdict(list)
    for row in rows:
        if row.source == "internal" and row.start_time < row.end_time:
            for kind in ("machine_id", "operator_id"):
                timelines[kind, getattr(row, kind)].append((row.start_time, row.end_time, row.op_id))
    for intervals in timelines.values():
        previous_end = None
        for start, end, _ in sorted(intervals):
            if previous_end is not None and start < previous_end:
                _block("candidate_resource_overlap", "候选内设备或人员安排重叠，不能正式采用。")
            previous_end = end


def adoption_downtimes(conn, prepared, payload):
    actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    rows = [row for row in payload.schedule_rows if row.source == "internal" and row.op_id not in actual]
    if not rows:
        return {}
    # Locked seeds may precede the requested run window. Prove every planned
    # arrangement against downtime at its own time and assigned machine.
    return load_machine_downtimes(ScheduleService(conn), algo_ops=rows,
                                 start_dt=min(row.start_time for row in rows))


def calendar_duration_conflict(calendar, row, op, batch, machine_downtimes):
    """按真实班次、效率、停机和工时从安排的开工时刻重算一遍；开完工对不上（或效率要兜底）即冲突。"""
    estimate = estimate_internal_slot(calendar=calendar, op=op, batch=batch,
        machine_id=row.machine_id, operator_id=row.operator_id, base_time=row.start_time,
        prev_end=row.start_time, machine_timeline=(), operator_timeline=(), end_dt_exclusive=None,
        machine_downtimes=machine_downtimes,
        last_op_type_by_machine=None, abort_after=None)
    return bool(estimate.efficiency_fallback_used or estimate.start_time != row.start_time
                or estimate.end_time != row.end_time)


def _internal(prepared, row, op, batch, validate_point, downtime):
    if row.start_time == row.end_time:
        validate_point(row)
        return
    if calendar_duration_conflict(prepared.cal_svc, row, op, batch, downtime.get(row.machine_id, ())):
        _block("candidate_calendar_duration_conflict", "候选开完工时间与真实班次、效率、停机或工时不一致。")


def adoption_external_intervals(prepared, *, algo_ops=None):
    groups = {op.id: merged_external_group_identity(op) for op in (prepared.algo_ops if algo_ops is None else algo_ops)}
    actual = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    cycles = merged_actual_group_intervals(groups, prepared.execution_seed_results, actual)
    return {op_id: cycles[identity] for op_id, identity in groups.items() if identity in cycles}


def external_holds_resources(row):
    """外协安排不能占本厂设备人员。"""
    return row.machine_id is not None or row.operator_id is not None


def _external(prepared, row, op, actual_intervals):
    if external_holds_resources(row):
        _block("candidate_external_resource_conflict", "外协候选带有未支持的内部资源占用。")
    actual_period = actual_intervals.get(row.op_id)
    days = op.ext_group_total_days if op.ext_merge_mode == "merged" else op.ext_days
    expected = actual_period if actual_period is not None else (row.start_time, prepared.cal_svc.add_calendar_days(row.start_time, days))
    if expected != (row.start_time, row.end_time):
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


def validate_adoption_constraints(conn, prepared, payload):
    checks = PreflightChecks(WorkbenchRunInputRepository(conn).adoption_check_tables())
    ops = {op.id: op for op in prepared.operations}
    algo_ops = {op.id: op for op in prepared.algo_ops}
    actual_ids = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    validate_point = candidate_point_validator(prepared)
    downtime = adoption_downtimes(conn, prepared, payload)
    actual_intervals = adoption_external_intervals(prepared)
    _resource_overlaps(payload.schedule_rows)
    for row in payload.schedule_rows:
        op, batch = ops[row.op_id], prepared.batches[ops[row.op_id].batch_id]
        raw = asdict(op)
        raw.update(machine_id=row.machine_id, operator_id=row.operator_id)
        # Actual production is a fact, not a duration that may be recomputed.
        # validate_candidate + execution guard retain its exact seed and identity.
        if _protected_arrangement(prepared, checks, row, raw, algo_ops[row.op_id], actual_ids, actual_intervals):
            continue
        code = arrangement_problem(checks, asdict(batch), raw, row.start_time, prepared.normalized_input)
        if code is not None:
            _block(code, _ARRANGEMENT_MESSAGES[code])
        if row.source == "internal":
            _internal(prepared, row, algo_ops[row.op_id], batch, validate_point, downtime)
        else:
            _external(prepared, row, algo_ops[row.op_id], actual_intervals)
