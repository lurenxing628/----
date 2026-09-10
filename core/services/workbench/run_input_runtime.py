"""Reuse runtime resource/freeze builders without accepting their degraded path."""

from datetime import datetime
from functools import partial

from core.services.scheduler.resource_pool_builder import (
    build_resource_pool,
    extend_downtime_map_for_resource_pool,
    load_machine_downtimes,
)
from core.services.scheduler.run.freeze_window import build_freeze_window_seed
from core.services.scheduler.run.schedule_input_runtime_support import (
    _build_runtime_support_inputs,
    _merge_execution_and_freeze_seed_results,
)
from core.services.workbench.preflight_checks import number, stored_date

from .plan_point_evidence import official_point_work
from .run_input_points import read_point_freeze_rows
from .run_input_rows import fail


def stored_point_validator(conn, version):
    work = None

    def validate(row):
        nonlocal work
        if work is None:
            work = official_point_work(conn, version)
        item = work.get(row.op_id)
        if item is None or not item["witness"].matches(row):
            fail("point_evidence_unproven", "Stored seed has no matching adopted point evidence.", op_id=row.op_id)
        return item["witness"]

    return validate


def _strict_pool(svc, *, cfg, algo_ops, meta):
    pool, warnings = build_resource_pool(svc, cfg=cfg, algo_ops=algo_ops, meta=meta)
    if cfg.auto_assign_enabled == "yes" and (pool is None or meta.get("resource_pool_build_ok") is not True):
        fail("resource_pool_unavailable", "Required auto-assignment resource pool could not be built.")
    return pool, warnings


def _locked_seeds(svc, operations, prev_version):
    by_id = {op.id: op for op in operations}
    latest = {}
    for row in svc.conn.execute("SELECT * FROM Schedule WHERE version<=? ORDER BY version,id", (prev_version,)):
        if row["op_id"] in by_id:
            latest[row["op_id"]] = row
    result = []
    for op_id, row in latest.items():
        if row["lock_status"] not in ("locked", "unlocked"):
            fail("invalid_schedule_lock", "Original schedule lock state is unknown.", op_id=op_id)
        if row["lock_status"] != "locked":
            continue
        op = by_id[op_id]
        start = svc._normalize_datetime(row["start_time"])
        end = svc._normalize_datetime(row["end_time"])
        if start is None or end is None or end < start:
            fail("invalid_locked_interval", "Locked original schedule has an invalid interval.", op_id=op_id)
        result.append({"op_id": op.id, "op_code": op.op_code, "batch_id": op.batch_id, "seq": op.seq,
                       "source": op.source, "op_type_name": op.op_type_name, "machine_id": row["machine_id"],
                       "operator_id": row["operator_id"], "start_time": start, "end_time": end})
        if start == end:
            from types import SimpleNamespace
            result[-1]["_point_evidence"] = stored_point_validator(svc.conn, row["version"])(SimpleNamespace(**result[-1]))
    return result


def _freeze_with_explicit_locks(svc, *, cfg, prev_version, start_dt, operations,
                                reschedulable_operations, strict_mode, meta):
    validator = stored_point_validator(svc.conn, prev_version)
    frozen, seeds, warnings = build_freeze_window_seed(
        svc, cfg=cfg, prev_version=prev_version, start_dt=start_dt, operations=operations,
        reschedulable_operations=reschedulable_operations, strict_mode=strict_mode, meta=meta,
        point_validator=validator,
        schedule_rows_reader=partial(read_point_freeze_rows, svc),
    )
    for seed in seeds:
        if seed["start_time"] == seed["end_time"]:
            from types import SimpleNamespace
            seed["_point_evidence"] = validator(SimpleNamespace(**seed))
    locked = _locked_seeds(svc, reschedulable_operations, prev_version)
    merged = _merge_execution_and_freeze_seed_results(execution_seed_results=locked, freeze_seed_results=seeds)
    locked_ids = {row["op_id"] for row in locked}
    meta["explicit_locked_op_ids"] = sorted(locked_ids)
    return set(frozen) | locked_ids, merged, warnings


def _validate_calendar_shifts(row, table):
    for field in ("shift_start", "shift_end"):
        value = row[field]
        if field == "shift_end" and value is None:
            continue
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except (TypeError, ValueError):
            fail("invalid_calendar_shift", "Stored shift time is unknown or invalid.", table=table, field=field)
        if parsed.strftime("%H:%M") != value:
            fail("invalid_calendar_shift", "Stored shift time must be canonical HH:MM.", table=table, field=field)


def _validate_calendar_row(row, table):
    if stored_date(row["date"]) is None:
        fail("invalid_calendar_date", "Stored calendar date is invalid.", table=table)
    for field in ("shift_hours", "efficiency"):
        if not number(row[field], positive=field == "efficiency"):
            fail("invalid_calendar_number", "Stored calendar capacity is unknown or invalid.", table=table, field=field)
    if row["day_type"] not in ("workday", "weekend", "holiday"):
        fail("invalid_calendar_state", "Stored calendar day type is unknown.", table=table)
    if row["allow_normal"] not in ("yes", "no") or row["allow_urgent"] not in ("yes", "no"):
        fail("invalid_calendar_state", "Stored calendar permission is unknown.", table=table)
    _validate_calendar_shifts(row, table)


def _validate_downtime_row(row):
    if row["status"] not in ("active", "cancelled"):
        fail("invalid_downtime_state", "Stored downtime state is unknown.")
    if row["status"] == "active":
        try:
            start, end = (datetime.fromisoformat(row[field]) for field in ("start_time", "end_time"))
        except (TypeError, ValueError):
            fail("invalid_downtime_interval", "Active downtime has invalid time values.")
        if start.tzinfo is not None or end.tzinfo is not None or end <= start:
            fail("invalid_downtime_interval", "Active downtime must be a positive local interval.")


def _validate_stored_runtime(conn):
    for table in ("WorkCalendar", "OperatorCalendar"):
        for row in conn.execute("SELECT * FROM " + table):
            _validate_calendar_row(row, table)
    for row in conn.execute("SELECT * FROM MachineDowntimes"):
        _validate_downtime_row(row)


def build_runtime(svc, *, cfg, prev_version, start_dt, batches, operations, mutable, algo_ops,
                  fixed_ids, completed_ids, execution_seeds, reservations):
    from .run_input_piece import input_piece_scope, validate_piece_seed_precedence

    scope = input_piece_scope(operations, batches)
    seed_validator = partial(validate_piece_seed_precedence, scope=scope, algo_ops=algo_ops) if scope is not None else None
    _validate_stored_runtime(svc.conn)
    return _build_runtime_support_inputs(
        svc, cfg=cfg, prev_version=prev_version, start_dt_norm=start_dt, run_label="candidate computation",
        batches=batches, operations=operations, reschedulable_operations=mutable, algo_ops=algo_ops,
        execution_fixed_op_ids=set(fixed_ids) | set(completed_ids), execution_completed_op_ids=completed_ids,
        execution_seed_results=execution_seeds, execution_reservations=reservations, strict_mode=True,
        build_freeze_window_seed_fn=_freeze_with_explicit_locks, load_machine_downtimes_fn=load_machine_downtimes,
        build_resource_pool_fn=_strict_pool, extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
        raise_schedule_empty_result_fn=lambda message, *, reason: fail(reason, message),
        validate_completed_seed_constraints_fn=seed_validator,
    )
