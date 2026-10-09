"""Reuse runtime resource/freeze builders without accepting their degraded path."""

from datetime import datetime
from functools import partial
from types import SimpleNamespace

from core.services.scheduler.resource_pool_builder import (
    build_resource_pool,
    extend_downtime_map_for_resource_pool,
    load_machine_downtimes,
)
from core.services.scheduler.run.freeze_window import build_freeze_window_seed
from core.services.scheduler.run.schedule_input_runtime_support import _build_runtime_support_inputs
from core.services.workbench.facts.preflight_checks import number, stored_date
from core.services.workbench.facts.run_input_rows import fail
from core.services.workbench.plan.point_evidence import official_point_work
from data.repositories.workbench_run_input_repo import WorkbenchRunInputRepository

from .input_points import read_point_freeze_rows


def stored_point_validator(conn, version):
    work = None

    def validate(row):
        nonlocal work
        if work is None:
            work = official_point_work(conn, version)
        item = work.get(row.op_id)
        if item is None or not item["witness"].matches(row):
            fail("point_evidence_unproven", "有零工时工序在正式计划里找不到对应依据，这次排产没有开始。请重新做排产检查后再排。", op_id=row.op_id)
        return item["witness"]

    return validate


def _strict_pool(svc, *, cfg, algo_ops, meta):
    pool, warnings = build_resource_pool(svc, cfg=cfg, algo_ops=algo_ops, meta=meta)
    if cfg.auto_assign_enabled == "yes" and (pool is None or meta.get("resource_pool_build_ok") is not True):
        fail("resource_pool_unavailable", "自动分配要用的设备人员清单建不起来，这次排产没有开始。请到资料总览核对设备和人员后重试。")
    return pool, warnings


def _occupies_machine(seed):
    # 外协和零工时安排不占设备时段，采用复核也不按停机检查。
    return seed["source"] == "internal" and bool(seed["machine_id"]) and seed["start_time"] < seed["end_time"]


def _overlaps(seed, intervals):
    return [(start, end) for start, end in intervals if start < seed["end_time"] and end > seed["start_time"]]


def held_machine_downtimes(svc, seeds):
    """保留安排所用设备的有效停机，与候选采用同一口径：按安排自己的设备，从最早一条安排起读。"""
    internal = [seed for seed in seeds if _occupies_machine(seed)]
    if not internal:
        return {}
    return load_machine_downtimes(svc, algo_ops=[SimpleNamespace(**seed) for seed in internal],
                                  start_dt=min(seed["start_time"] for seed in internal))


def downtime_overlap(seed, downtimes):
    """保留的原安排排产时原样保留、不会避开停机；采用时却按停机复核，两者重叠的候选都采用不了。

    返回第一段压在这条安排上的停机；外协和零工时安排不占设备，返回 None。
    """
    if not _occupies_machine(seed):
        return None
    overlaps = _overlaps(seed, downtimes.get(str(seed["machine_id"]).strip(), ()))
    return overlaps[0] if overlaps else None


def _freeze_hold_window(svc, *, cfg, prev_version, start_dt, operations, reschedulable_operations, strict_mode, meta,
                        hold_window=None, hold_start=None):
    """只按本次的不重排时段保留原安排。正式计划里的锁定标记（旧版「锁定近期排程」顺带打上的）不再起作用：
    已开工、做完的工序由报工记录保护，其余工序要不要保持原安排，每次排产由不重排时段决定。"""
    validator = stored_point_validator(svc.conn, prev_version)
    frozen, seeds, warnings = build_freeze_window_seed(
        # hold_start：试调采用按来源排产的起日起算冻结（同批前道从那天起找），与来源排产同一口径。
        svc, cfg=cfg, prev_version=prev_version, start_dt=hold_start or start_dt, operations=operations,
        reschedulable_operations=reschedulable_operations, strict_mode=strict_mode, meta=meta,
        point_validator=validator,
        schedule_rows_reader=partial(read_point_freeze_rows, svc),
        # 前道原安排不在排产起日之后（排产起日前还没报工，或者没排过）的批次整批前后顺序保不住：
        # 这批本次不保留、照常重排，排产检查事先提醒；其它原安排读不出来仍整次拒绝。
        skip_incomplete_prefix=True,
        # 工作台的配置副本已关掉按天数冻结；不重排时段为 None 时这里就不保留任何时段内的原安排。
        hold_window=hold_window,
    )
    for seed in seeds:
        if seed["start_time"] == seed["end_time"]:
            seed["_point_evidence"] = validator(SimpleNamespace(**seed))
    return set(frozen), seeds, warnings


def held_arrangements(svc, *, cfg, prev_version, start_dt, operations, reschedulable_operations, hold_window=None):
    """排产会原样保留的原安排：落在本次不重排时段里的（含同批次一起保留的前道）；与排产计算同一口径、同样严格。

    返回 (保留安排, 保留信息)；保留信息里 hold_window 是本次的不重排时段，freeze_skipped_batch_ids 是前道原安排不全、
    这次不保留的批次。原安排读不出来抛 ValidationError（field=freeze_window）。
    """
    meta = {}
    _, seeds, _ = _freeze_hold_window(
        svc, cfg=cfg, prev_version=prev_version, start_dt=start_dt, operations=operations,
        reschedulable_operations=reschedulable_operations, strict_mode=True, meta=meta, hold_window=hold_window)
    return seeds, meta


def _blank(value):
    # 旧库升级加列时没有回填：空着的班次开始、工时、效率由日历引擎按默认值解释
    # （08:00 开始、工时按时段或起止推算否则 8 小时、效率 1），日历页同样这样显示，排产不另拒。
    return value is None or isinstance(value, str) and not value.strip()


def _validate_calendar_shifts(row, table):
    for field in ("shift_start", "shift_end"):
        value = row[field]
        if _blank(value):
            continue
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except (TypeError, ValueError):
            fail("invalid_calendar_shift", "工作日历里有班次时间读不出来或者填得不对，这次排产没有开始。请到工作日历按 08:30 这样改好。", table=table, field=field)
        if parsed.strftime("%H:%M") != value:
            fail("invalid_calendar_shift", "工作日历里的班次时间格式不对，这次排产没有开始。请按 08:30 这样填。", table=table, field=field)


def _validate_calendar_row(row, table):
    if stored_date(row["date"]) is None:
        fail("invalid_calendar_date", "工作日历里有日期填得不对，这次排产没有开始。请按 2026-09-13 这样改好。", table=table)
    for field in ("shift_hours", "efficiency"):
        if not _blank(row[field]) and not number(row[field], positive=field == "efficiency"):
            fail("invalid_calendar_number", "工作日历里有班次工时或效率读不出来，这次排产没有开始。请到工作日历补上。", table=table, field=field)
    if row["day_type"] not in ("workday", "weekend", "holiday"):
        fail("invalid_calendar_state", "工作日历里有日期类型认不出来，这次排产没有开始。请到工作日历重新选工作日、周末或假期。", table=table)
    if row["allow_normal"] not in ("yes", "no") or row["allow_urgent"] not in ("yes", "no"):
        fail("invalid_calendar_state", "工作日历里普通件或急件的许可认不出来，这次排产没有开始。请到工作日历重新设置。", table=table)
    _validate_calendar_shifts(row, table)


def _validate_downtime_row(row):
    if row["status"] not in ("active", "cancelled"):
        fail("invalid_downtime_state", "停机记录的状态认不出来，这次排产没有开始。请到工作日历核对停机记录。")
    if row["status"] == "active":
        try:
            start, end = (datetime.fromisoformat(row[field]) for field in ("start_time", "end_time"))
        except (TypeError, ValueError):
            fail("invalid_downtime_interval", "有生效的停机记录时间填得不对，这次排产没有开始。请到工作日历按 2026-09-13 08:30 这样改好。")
        if start.tzinfo is not None or end.tzinfo is not None or end <= start:
            fail("invalid_downtime_interval", "有生效的停机记录结束时间不比开始时间晚，这次排产没有开始。请到工作日历改好起止时间。")


def _validate_stored_runtime(conn):
    repo = WorkbenchRunInputRepository(conn)
    for table, row in repo.calendar_rows():
        _validate_calendar_row(row, table)
    for row in repo.machine_downtime_rows():
        _validate_downtime_row(row)


def build_runtime(svc, *, cfg, prev_version, start_dt, batches, operations, mutable, algo_ops,
                  fixed_ids, completed_ids, execution_seeds, reservations, hold_window=None, hold_start=None):
    from .input_piece import input_piece_scope, validate_piece_seed_precedence

    scope = input_piece_scope(operations, batches)
    seed_validator = partial(validate_piece_seed_precedence, scope=scope, algo_ops=algo_ops) if scope is not None else None
    _validate_stored_runtime(svc.conn)
    return _build_runtime_support_inputs(
        svc, cfg=cfg, prev_version=prev_version, start_dt_norm=start_dt, run_label="排产计算",
        batches=batches, operations=operations, reschedulable_operations=mutable, algo_ops=algo_ops,
        execution_fixed_op_ids=set(fixed_ids) | set(completed_ids), execution_completed_op_ids=completed_ids,
        execution_seed_results=execution_seeds, execution_reservations=reservations, strict_mode=True,
        build_freeze_window_seed_fn=partial(_freeze_hold_window, hold_window=hold_window, hold_start=hold_start),
        load_machine_downtimes_fn=load_machine_downtimes,
        build_resource_pool_fn=_strict_pool, extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
        raise_schedule_empty_result_fn=lambda message, *, reason: fail(reason, message),
        validate_completed_seed_constraints_fn=seed_validator,
    )
