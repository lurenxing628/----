"""Reuse runtime resource/freeze builders without accepting their degraded path."""

from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Set, Tuple

from core.algorithm_contracts.types import ScheduleResult
from core.errors import ValidationError
from core.models.calendar_periods import decode_periods
from core.services.scheduler.resource_pool_builder import (
    CapturedResourceFacts,
    build_resource_pool,
    extend_downtime_map_for_resource_pool,
    load_machine_downtimes,
)
from core.services.scheduler.run.freeze_window import build_freeze_window_seed
from core.services.scheduler.run.schedule_input_runtime_support import (
    _load_runtime_resource_inputs,
    prepare_runtime_seeds,
)
from core.services.workbench.facts.run_input_rows import fail
from core.shared.stored_dates import stored_date, stored_local_iso_datetime
from core.shared.strict_parse import is_stored_number

from .input_points import read_point_freeze_rows


@dataclass
class HeldArrangements:
    frozen_op_ids: Set[int]
    seed_results: List[Dict[str, Any]]
    meta: Dict[str, Any]


@dataclass(frozen=True)
class RuntimeResourceInputs:
    resources: CapturedResourceFacts
    downtimes: Dict[str, List[Tuple[datetime, datetime]]]


def stored_point_validator(facts, version):
    work = None

    def validate(row):
        nonlocal work
        if work is None:
            context = facts.official_source(version)
            reader = context.get("point_work") if context is not None else None
            work = reader() if reader is not None else {}
        item = work.get(row.op_id)
        if item is None or not item["witness"].matches(row):
            fail("point_evidence_unproven", "有零工时工序在正式计划里找不到对应依据，这次排产没有开始。请重新做排产检查后再排。", op_id=row.op_id)
        return item["witness"]

    return validate


def _occupies_machine(seed):
    # 外协和零工时安排不占设备时段，采用复核也不按停机检查。设备号来自排程外键或已准入的实际报工，非空即真实设备。
    return seed["source"] == "internal" and seed["machine_id"] is not None and seed["start_time"] < seed["end_time"]


def _overlaps(seed, intervals):
    return [(start, end) for start, end in intervals if start < seed["end_time"] and end > seed["start_time"]]


def held_machine_downtimes(seeds, *, facts):
    """保留安排所用设备的有效停机，与候选采用同一口径：按安排自己的设备，从最早一条安排起读。"""
    internal = [seed for seed in seeds if _occupies_machine(seed)]
    if not internal:
        return {}
    return load_machine_downtimes(algo_ops=[ScheduleResult(**seed) for seed in internal],
                                  start_dt=min(seed["start_time"] for seed in internal),
                                  downtimes=runtime_resource_inputs(facts).downtimes)


def downtime_overlap(seed, downtimes):
    """保留的原安排排产时原样保留、不会避开停机；采用时却按停机复核，两者重叠的候选都采用不了。

    返回第一段压在这条安排上的停机；外协和零工时安排不占设备，返回 None。
    """
    if not _occupies_machine(seed):
        return None
    overlaps = _overlaps(seed, downtimes.get(seed["machine_id"], ()))
    return overlaps[0] if overlaps else None


def _freeze_hold_window(*, facts, prev_version, start_dt, reschedulable_operations, meta, hold_window):
    """只按本次的不重排时段保留原安排。正式计划里的锁定标记（旧版「锁定近期排程」顺带打上的）不再起作用：
    已开工、做完的工序由报工记录保护，其余工序要不要保持原安排，每次排产由不重排时段决定。

    前道原安排不在排产起日之后（排产起日前还没报工，或者没排过）的批次整批前后顺序保不住：
    这批本次不保留、照常重排，排产检查事先提醒；其它原安排读不出来仍整次拒绝。
    """
    return build_freeze_window_seed(
        # 试调在来源排产起日上准备这份冻结结果，与来源排产同一口径。
        prev_version=prev_version, start_dt=start_dt,
        reschedulable_operations=reschedulable_operations, meta=meta,
        # 零工时点事件的见证在冻结前缀校验时取一次，随 seed 的 _point_evidence 带出。
        point_validator=stored_point_validator(facts, prev_version),
        schedule_rows_reader=partial(read_point_freeze_rows, facts=facts),
        # 工作台的配置副本已关掉按天数冻结；不重排时段为 None 时这里就不保留任何时段内的原安排。
        hold_window=hold_window,
    )


def held_arrangements(*, facts, prev_version, start_dt, reschedulable_operations, hold_window):
    """排产会原样保留的原安排：落在本次不重排时段里的（含同批次一起保留的前道）；与排产计算同一口径、同样严格。

    返回完整冻结结果；保留信息里 hold_window 是本次的不重排时段，freeze_skipped_batch_ids 是前道原安排不全、
    这次不保留的批次。原安排读不出来抛 ValidationError（field=freeze_window）。
    """
    freeze_meta = {}
    frozen, seeds = _freeze_hold_window(
        facts=facts, prev_version=prev_version, start_dt=start_dt,
        reschedulable_operations=reschedulable_operations, meta=freeze_meta, hold_window=hold_window)
    return HeldArrangements(frozen, seeds, freeze_meta)


def _validate_calendar_row(row, table, decoded_periods):
    """存储行在进入排产前准入一次：工作时段是唯一的时间事实，起止与工时都由它现算，不另存、不另查。"""
    if stored_date(row["date"]) is None:
        fail("invalid_calendar_date", "工作日历里有日期填得不对，这次排产没有开始。请按 2026-09-13 这样改好。", table=table)
    if not is_stored_number(row["efficiency"], positive=True):
        fail("invalid_calendar_number", "工作日历里有效率读不出来，这次排产没有开始。请到工作日历补上。", table=table, field="efficiency")
    if row["day_type"] not in ("workday", "weekend", "holiday"):
        fail("invalid_calendar_state", "工作日历里有日期类型认不出来，这次排产没有开始。请到工作日历重新选工作日、周末或假期。", table=table)
    if row["allow_normal"] not in ("yes", "no") or row["allow_urgent"] not in ("yes", "no"):
        fail("invalid_calendar_state", "工作日历里普通件或急件的许可认不出来，这次排产没有开始。请到工作日历重新设置。", table=table)
    raw_periods = row["periods_json"]
    if type(raw_periods) is not str or raw_periods not in decoded_periods:
        try:
            decoded = decode_periods(raw_periods)
        except ValidationError:
            fail("invalid_calendar_shift", "工作日历里的工作时段读不出来或者填得不对，这次排产没有开始。请到工作日历重新设置。",
                 table=table, field="periods_json")
        decoded_periods[raw_periods] = decoded


def _validate_downtime_row(row):
    if row["status"] not in ("active", "cancelled"):
        fail("invalid_downtime_state", "停机记录的状态认不出来，这次排产没有开始。请到工作日历核对停机记录。")
    if row["status"] == "active":
        start = stored_local_iso_datetime(row["start_time"], allow_space=True, allow_minutes_only=True)
        end = stored_local_iso_datetime(row["end_time"], allow_space=True, allow_minutes_only=True)
        if start is None or end is None:
            fail("invalid_downtime_interval", "有生效的停机记录时间填得不对，这次排产没有开始。请到工作日历按 2026-09-13 08:30 这样改好。")
        if end <= start:
            fail("invalid_downtime_interval", "有生效的停机记录结束时间不比开始时间晚，这次排产没有开始。请到工作日历改好起止时间。")
        return start, end


def runtime_resource_inputs(facts) -> RuntimeResourceInputs:
    """Prepare each stored runtime row once under its production capture owner."""
    capture = facts.capture
    if capture.runtime_resources is None:
        for table in ("WorkCalendar", "OperatorCalendar"):
            for row in capture.table(table):
                _validate_calendar_row(row, table, capture.decoded_periods)
        downtimes: Dict[str, List[Tuple[datetime, datetime]]] = {}
        for row in capture.table("MachineDowntimes"):
            interval = _validate_downtime_row(row)
            # 停机的设备号是 NOT NULL 外键，按库里原值分组。
            if interval is not None:
                downtimes.setdefault(row["machine_id"], []).append(interval)
        for intervals in downtimes.values():
            intervals.sort(key=lambda interval: interval[0])
        capture.runtime_resources = RuntimeResourceInputs(
            resources=capture.resource_facts(),
            downtimes=downtimes,
        )
    return capture.runtime_resources


def build_runtime(conn, *, facts, cfg, prev_version, start_dt, batches, operations, mutable, algo_ops,
                  completed_ids, execution_seeds, hold_window, piece_scope,
                  for_adoption: bool, held):
    from .input_piece import validate_piece_seed_precedence

    seed_validator = partial(validate_piece_seed_precedence, scope=piece_scope) if piece_scope is not None else None
    runtime = runtime_resource_inputs(facts)
    resources = runtime.resources
    if held is None:
        held = held_arrangements(
            facts=facts, prev_version=prev_version, start_dt=start_dt,
            reschedulable_operations=mutable, hold_window=hold_window)
    frozen, seeds, to_schedule = prepare_runtime_seeds(
        conn, run_label="排产计算", batches=batches, operations=operations, algo_ops=algo_ops,
        frozen_op_ids=held.frozen_op_ids, freeze_seed_results=held.seed_results,
        execution_completed_op_ids=completed_ids,
        execution_seed_results=execution_seeds,
        raise_schedule_empty_result_fn=lambda message, *, reason: fail(reason, message),
        validate_completed_seed_constraints_fn=seed_validator,
        validate_fixed_operator_qualifications_fn=resources.validate_fixed,
    )
    if for_adoption:
        return frozen, seeds, held.meta, [], {}, {}, {}, None, 0
    downtime_meta, pool_meta, downtime, pool = _load_runtime_resource_inputs(
        cfg=cfg, algo_ops=algo_ops, resource_pool_ops=to_schedule, start_dt_norm=start_dt,
        load_machine_downtimes_fn=partial(load_machine_downtimes, downtimes=runtime.downtimes),
        build_resource_pool_fn=partial(build_resource_pool, resource_facts=resources),
        extend_downtime_map_for_resource_pool_fn=partial(extend_downtime_map_for_resource_pool,
                                                         downtimes=runtime.downtimes),
    )
    seed_version = max(int(prev_version) + 1, 1)
    return frozen, seeds, held.meta, to_schedule, downtime_meta, pool_meta, downtime, pool, seed_version
