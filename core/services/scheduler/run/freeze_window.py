from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.errors import ValidationError
from core.models.enums import YesNo
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.models.scheduler_degradation_messages import FREEZE_WINDOW_DEGRADED_MESSAGE
from core.shared.boolean_normalize import to_yes_no
from core.shared.local_datetime import format_local_datetime as fmt_dt

from .freeze_window_prefixes import (
    group_seed_operations_by_batch,
    prefix_op_ids_for_anchors,
    rows_in_window,
    window_anchors_by_batch,
)
from .freeze_window_seed_rows import (
    build_seed_results as _build_seed_results,
)
from .freeze_window_seed_rows import (
    cache_seed_for_prefix as _cache_seed_for_prefix,
)

_FREEZE_DEGRADATION_CODE = "freeze_seed_unavailable"
_FREEZE_CONFIG_FIELDS = {"freeze_window_enabled", "freeze_window_days"}
_FREEZE_DISABLED_CONFIG_DISABLED = "config_disabled"
_FREEZE_DISABLED_NO_DAYS = "no_days"
_FREEZE_DISABLED_NO_PREVIOUS_VERSION = "no_previous_version"
_FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS = "no_reschedulable_operations"
_FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS = "no_previous_schedule_rows"
_FREEZE_DISABLED_NO_FREEZABLE_PREFIX = "no_freezable_prefix"


@dataclass(frozen=True)
class _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]]
    invalid_row_count: int


@dataclass(frozen=True)
class _FreezeSeedScope:
    start_str: str
    freeze_end_str: str
    seed_operations_by_batch: Dict[str, List[Any]]
    op_by_id: Dict[int, Any]
    op_ids_all: List[int]
    # 调用方指定的时段：只有和 [anchor_start, anchor_end) 重叠的原安排算"要保留"，同批次前道从 start_str 起补齐。
    # 为 None 时沿用旧口径：读到的窗口内原安排都算。
    anchor_start: Optional[datetime] = None
    anchor_end: Optional[datetime] = None


def _init_freeze_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    meta.setdefault("freeze_state", "disabled")
    meta.setdefault("freeze_applied", False)
    meta.setdefault("freeze_enabled", False)
    meta.setdefault("freeze_days", 0)
    meta.setdefault("freeze_disabled_reason", None)
    return meta


def _freeze_config_degraded(cfg: ScheduleConfigSnapshot) -> bool:
    # 配置快照的降级事件统一由 degradation_events_to_dicts 生成：field 为字段名或 None，code 为规范代码。
    return any(event["field"] in _FREEZE_CONFIG_FIELDS or event["code"] == _FREEZE_DEGRADATION_CODE
               for event in cfg.degradation_events)


def _set_freeze_disabled(meta: Dict[str, Any], reason: str) -> None:
    meta["freeze_state"] = "disabled"
    meta["freeze_disabled_reason"] = reason


def _freeze_window_days(cfg: Any, prev_version: int, *, meta: Dict[str, Any]) -> int:
    if _freeze_config_degraded(cfg):
        raise _freeze_unavailable()
    enabled = to_yes_no(cfg.freeze_window_enabled, default=YesNo.NO.value) == YesNo.YES.value
    meta["freeze_enabled"] = bool(enabled)
    days = int(cfg.freeze_window_days or 0)
    meta["freeze_days"] = int(days)

    if not enabled:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_CONFIG_DISABLED)
        meta["freeze_days"] = 0
        return 0
    if days <= 0:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_NO_DAYS)
        return 0
    if int(prev_version or 0) <= 0:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_NO_PREVIOUS_VERSION)
        return 0
    return int(days)


def _freeze_unavailable() -> ValidationError:
    # 上一版计划的存储数据或冻结配置读不出来：整次拒绝，不降级成部分冻结。
    return ValidationError(FREEZE_WINDOW_DEGRADED_MESSAGE, field="freeze_window")


def _set_freeze_applied(meta: Dict[str, Any], frozen_op_ids: Set[int]) -> None:
    meta["freeze_applied"] = bool(frozen_op_ids)


def _load_schedule_map(
    *,
    prev_version: int,
    op_ids: List[int],
    start_str: str,
    freeze_end_str: str,
    schedule_rows_reader: Any,
) -> _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]] = {}
    invalid_row_count = 0
    duplicate_op_ids: Set[int] = set()
    rows = schedule_rows_reader(
        version=int(prev_version),
        op_ids=op_ids,
        start_time=start_str,
        end_time=freeze_end_str,
    )
    for row in rows:
        try:
            row_dict = row if isinstance(row, dict) else dict(row)
            oid = int(row_dict.get("op_id") or 0)
            if oid <= 0:
                raise ValueError("op_id must be positive")
            if oid in schedule_map or oid in duplicate_op_ids:
                duplicate_op_ids.add(int(oid))
                schedule_map.pop(int(oid), None)
                invalid_row_count += 1
                continue
            schedule_map[int(oid)] = row_dict
        except Exception:
            invalid_row_count += 1
    return _LoadedScheduleMapOutcome(
        schedule_map=schedule_map,
        invalid_row_count=int(invalid_row_count),
    )


def _empty_freeze_seed_result(freeze_meta: Dict[str, Any]) -> Tuple[Set[int], List[Dict[str, Any]]]:
    _set_freeze_applied(freeze_meta, set())
    return set(), []


def _hold_window_days(hold_window: Tuple[datetime, datetime], start_dt: datetime, prev_version: int,
                      meta: Dict[str, Any]) -> int:
    """调用方指定时段时不看配置里的天数；天数只给旧诊断字段一个正数口径。"""
    meta["freeze_enabled"] = True
    meta["hold_window"] = (hold_window[0], hold_window[1])
    days = math.ceil((hold_window[1] - start_dt).total_seconds() / 86400) if hold_window[1] > start_dt else 0
    meta["freeze_days"] = int(days)
    if days <= 0:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_NO_DAYS)
        return 0
    if int(prev_version or 0) <= 0:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_NO_PREVIOUS_VERSION)
        return 0
    return int(days)


def _prepare_freeze_seed_scope(
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    seed_operations: List[Any],
    freeze_meta: Dict[str, Any],
    hold_window: Optional[Tuple[datetime, datetime]],
) -> Optional[_FreezeSeedScope]:
    if hold_window is not None:
        freeze_days = _hold_window_days(hold_window, start_dt, prev_version, freeze_meta)
    else:
        freeze_days = _freeze_window_days(cfg, prev_version, meta=freeze_meta)
    if freeze_days <= 0:
        return None

    freeze_end = hold_window[1] if hold_window is not None else start_dt + timedelta(days=freeze_days)
    seed_operations_by_batch = group_seed_operations_by_batch(seed_operations)
    op_by_id: Dict[int, Any] = {int(op.id): op for op in seed_operations if op and op.id}
    op_ids_all = sorted(op_by_id)
    if not op_ids_all:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS)
        return None

    return _FreezeSeedScope(
        start_str=fmt_dt(start_dt),
        freeze_end_str=fmt_dt(freeze_end),
        seed_operations_by_batch=seed_operations_by_batch,
        op_by_id=op_by_id,
        op_ids_all=op_ids_all,
        anchor_start=hold_window[0] if hold_window is not None else None,
        anchor_end=hold_window[1] if hold_window is not None else None,
    )


def _load_previous_schedule_for_freeze(
    *,
    scope: _FreezeSeedScope,
    prev_version: int,
    freeze_meta: Dict[str, Any],
    schedule_rows_reader: Any,
) -> Optional[_LoadedScheduleMapOutcome]:
    try:
        load_outcome = _load_schedule_map(
            prev_version=int(prev_version),
            op_ids=scope.op_ids_all,
            start_str=scope.start_str,
            freeze_end_str=scope.freeze_end_str,
            schedule_rows_reader=schedule_rows_reader,
        )
    except Exception as exc:
        raise _freeze_unavailable() from exc

    if load_outcome.invalid_row_count > 0:
        raise _freeze_unavailable()

    if not load_outcome.schedule_map:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS)
        return None

    return load_outcome


def _apply_freeze_prefixes(
    *,
    scope: _FreezeSeedScope,
    schedule_map: Dict[int, Dict[str, Any]],
    seed_tmp: Dict[int, Dict[str, Any]],
    freeze_meta: Dict[str, Any],
    point_validator: Any,
) -> Set[int]:
    frozen_op_ids: Set[int] = set()
    anchors_lookup = window_anchors_by_batch(
        rows_in_window(scope.anchor_start, scope.anchor_end, schedule_map), scope.op_by_id)

    for bid, anchors in anchors_lookup.items():
        prefix = prefix_op_ids_for_anchors(scope.seed_operations_by_batch.get(bid, []), bid, anchors)
        if any(oid not in schedule_map for oid in prefix):
            # 前道原安排不在冻结窗口里（窗口前还没报工，或者没排过）的批次整批不冻结、照常重排，
            # 由调用方事先提醒；窗口内读到的行本身没有坏，不整次拒绝。
            freeze_meta.setdefault("freeze_skipped_batch_ids", []).append(bid)
            continue

        if _cache_seed_for_prefix(prefix=prefix, schedule_map=schedule_map, op_by_id=scope.op_by_id,
                                  seed_tmp=seed_tmp, point_validator=point_validator):
            raise _freeze_unavailable()

        for oid in prefix:
            frozen_op_ids.add(int(oid))

    return frozen_op_ids


def _finish_freeze_seed_result(
    frozen_op_ids: Set[int],
    *,
    scope: _FreezeSeedScope,
    seed_tmp: Dict[int, Dict[str, Any]],
    freeze_meta: Dict[str, Any],
) -> Tuple[Set[int], List[Dict[str, Any]]]:
    seed_results = _build_seed_results(frozen_op_ids, op_by_id=scope.op_by_id, seed_tmp=seed_tmp)

    if frozen_op_ids:
        freeze_meta["freeze_state"] = "active"
    else:
        # 一个前缀都没冻住（如上一版窗内命中行全部对应 seq<=0 工序，被
        # freeze_window_prefixes.window_anchors_by_batch 跳过，或前道不全的批次全被跳过）。补上
        # reason，保住"disabled 必带可查原因"的诊断口径（audit 2026-07-20 A15）。
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_FREEZABLE_PREFIX)
    _set_freeze_applied(freeze_meta, frozen_op_ids)
    return frozen_op_ids, seed_results


def build_freeze_window_seed(
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    reschedulable_operations: List[Any],
    meta: Dict[str, Any],
    point_validator: Any,
    schedule_rows_reader: Any,
    hold_window: Optional[Tuple[datetime, datetime]] = None,
) -> Tuple[Set[int], List[Dict[str, Any]]]:
    """上一版计划读不出来或冻结前缀有坏行时抛 ValidationError(field="freeze_window")，不降级成部分冻结。

    前道原安排不在窗口里的批次不冻结、记进 meta["freeze_skipped_batch_ids"]。
    hold_window=(开始, 结束) 时不看配置里的冻结开关和天数：和这段时间重叠的原安排保留，同批次排在前面的
    从 start_dt 起读到的原安排一起保留；记进 meta["hold_window"]。为 None 时按配置里的冻结天数。
    """
    freeze_meta = _init_freeze_meta(meta)

    scope = _prepare_freeze_seed_scope(
        cfg=cfg,
        prev_version=int(prev_version),
        start_dt=start_dt,
        seed_operations=reschedulable_operations,
        freeze_meta=freeze_meta,
        hold_window=hold_window,
    )
    if scope is None:
        return _empty_freeze_seed_result(freeze_meta)

    load_outcome = _load_previous_schedule_for_freeze(
        scope=scope,
        prev_version=int(prev_version),
        freeze_meta=freeze_meta,
        schedule_rows_reader=schedule_rows_reader,
    )
    if load_outcome is None:
        return _empty_freeze_seed_result(freeze_meta)

    seed_tmp: Dict[int, Dict[str, Any]] = {}
    frozen_op_ids = _apply_freeze_prefixes(
        scope=scope,
        schedule_map=load_outcome.schedule_map,
        seed_tmp=seed_tmp,
        freeze_meta=freeze_meta,
        point_validator=point_validator,
    )
    return _finish_freeze_seed_result(
        frozen_op_ids,
        scope=scope,
        seed_tmp=seed_tmp,
        freeze_meta=freeze_meta,
    )
