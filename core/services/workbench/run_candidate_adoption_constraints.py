"""Prove resources, occupied intervals, calendar duration and readiness explicitly."""

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.models.workbench_run_adoption import CandidateAdoptionBlocked

from .preflight_checks import PreflightChecks, stored_date
from .zero_duration import candidate_point_validator

_TABLES = ("Machines", "Operators", "Suppliers", "OpTypes", "OperatorMachine", "OperatorSkill",
           "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes", "PartOperations", "ExternalGroups", "BatchMaterials")


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


def _internal(prepared, row, op, batch, validate_point):
    if row.start_time == row.end_time:
        validate_point(row)
        return
    estimate = estimate_internal_slot(calendar=prepared.cal_svc, op=op, batch=batch,
        machine_id=row.machine_id, operator_id=row.operator_id, base_time=row.start_time,
        prev_end=row.start_time, machine_timeline=(), operator_timeline=(), end_dt_exclusive=None,
        machine_downtimes=prepared.downtime_map.get(row.machine_id, ()),
        last_op_type_by_machine=None, abort_after=None)
    if (estimate.efficiency_fallback_used or estimate.start_time != row.start_time
            or estimate.end_time != row.end_time):
        _block("candidate_calendar_duration_conflict", "候选开完工时间与真实班次、效率、停机或工时不一致。")


def _external(prepared, row, op):
    if row.machine_id is not None or row.operator_id is not None:
        _block("candidate_external_resource_conflict", "外协候选带有未支持的内部资源占用。")
    days = op.ext_group_total_days if op.ext_merge_mode == "merged" else op.ext_days
    if prepared.cal_svc.add_calendar_days(row.start_time, days) != row.end_time:
        _block("candidate_external_duration_conflict", "外协候选与真实外协周期不一致。")


def validate_adoption_constraints(conn, prepared, payload):
    checks = PreflightChecks({name: [dict(row) for row in conn.execute('SELECT * FROM "' + name + '"')]
                              for name in _TABLES})
    ops = {op.id: op for op in prepared.operations}
    algo_ops = {op.id: op for op in prepared.algo_ops}
    actual_ids = prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    validate_point = candidate_point_validator(prepared)
    _resource_overlaps(payload.schedule_rows)
    for row in payload.schedule_rows:
        op, batch = ops[row.op_id], prepared.batches[ops[row.op_id].batch_id]
        raw = asdict(op)
        raw.update(machine_id=row.machine_id, operator_id=row.operator_id)
        if checks.fields(asdict(batch), raw) or checks.resources(raw):
            _block("candidate_resource_invalid", "候选实际使用的设备、人员资质、工种或供应商不合法。")
        # Actual production is a fact, not a duration that may be recomputed.
        # validate_candidate + execution guard retain its exact seed and identity.
        if row.op_id in actual_ids:
            continue
        if checks.readiness(asdict(batch), prepared.readiness_gate_enabled):
            _block("candidate_material_not_ready", "候选仍有未齐套物料，不能正式采用。")
        # SQLite DECLTYPES returns date objects in the application; snapshots use ISO text.
        # batch_model has already rejected invalid dates using the same parser.
        ready_day = stored_date(batch.ready_date)
        if ready_day is not None and row.start_time < datetime.fromisoformat(ready_day):
            _block("candidate_before_ready_date", "候选安排早于实际可开工日期。")
        if row.source == "internal":
            _internal(prepared, row, algo_ops[row.op_id], batch, validate_point)
        else:
            _external(prepared, row, algo_ops[row.op_id])
