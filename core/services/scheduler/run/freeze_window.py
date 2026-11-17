from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

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

_FREEZE_DISABLED_CONFIG_DISABLED = "config_disabled"
_FREEZE_DISABLED_NO_DAYS = "no_days"
_FREEZE_DISABLED_NO_PREVIOUS_VERSION = "no_previous_version"
_FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS = "no_reschedulable_operations"
_FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS = "no_previous_schedule_rows"
_FREEZE_DISABLED_NO_FREEZABLE_PREFIX = "no_freezable_prefix"


@dataclass(frozen=True)
class _FreezeSeedScope:
    read_start: datetime
    read_end: datetime
    seed_operations_by_batch: Dict[str, List[Any]]
    op_by_id: Dict[int, Any]
    op_ids_all: List[int]
    anchor_start: datetime
    anchor_end: datetime


def _init_freeze_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    meta.setdefault("freeze_state", "disabled")
    meta.setdefault("freeze_applied", False)
    meta.setdefault("freeze_enabled", False)
    meta.setdefault("freeze_days", 0)
    meta.setdefault("freeze_disabled_reason", None)
    return meta


def _set_freeze_disabled(meta: Dict[str, Any], reason: str) -> None:
    meta["freeze_state"] = "disabled"
    meta["freeze_disabled_reason"] = reason


def _set_freeze_applied(meta: Dict[str, Any], frozen_op_ids: Set[int]) -> None:
    meta["freeze_applied"] = bool(frozen_op_ids)


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
    if prev_version <= 0:
        _set_freeze_disabled(meta, _FREEZE_DISABLED_NO_PREVIOUS_VERSION)
        return 0
    return int(days)


def _prepare_freeze_seed_scope(
    *,
    prev_version: int,
    start_dt: datetime,
    seed_operations: List[Any],
    freeze_meta: Dict[str, Any],
    hold_window: Optional[Tuple[datetime, datetime]],
) -> Optional[_FreezeSeedScope]:
    if hold_window is None:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_CONFIG_DISABLED)
        return None
    freeze_days = _hold_window_days(hold_window, start_dt, prev_version, freeze_meta)
    if freeze_days <= 0:
        return None

    freeze_end = hold_window[1]
    seed_operations_by_batch = group_seed_operations_by_batch(seed_operations)
    op_by_id: Dict[int, Any] = {int(op.id): op for op in seed_operations}
    op_ids_all = sorted(op_by_id)
    if not op_ids_all:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS)
        return None

    return _FreezeSeedScope(
        read_start=start_dt,
        read_end=freeze_end,
        seed_operations_by_batch=seed_operations_by_batch,
        op_by_id=op_by_id,
        op_ids_all=op_ids_all,
        anchor_start=hold_window[0],
        anchor_end=hold_window[1],
    )


def _load_previous_schedule_for_freeze(
    *,
    scope: _FreezeSeedScope,
    prev_version: int,
    freeze_meta: Dict[str, Any],
    schedule_rows_reader: Any,
) -> Optional[Dict[int, Dict[str, Any]]]:
    """{工序: 上一版排程行}：读取器只返回 op_ids 里的工序在这一版的行，同一版同一工序只有一行（Schedule(version, op_id) 唯一）。"""
    rows = schedule_rows_reader(
        version=prev_version,
        op_ids=scope.op_ids_all,
        start_time=scope.read_start,
        end_time=scope.read_end,
    )
    schedule_map = {row["op_id"]: row for row in rows}
    if not schedule_map:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS)
        return None
    return schedule_map


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
        prefix = prefix_op_ids_for_anchors(scope.seed_operations_by_batch[bid], anchors)
        if any(oid not in schedule_map for oid in prefix):
            # 前道原安排不在冻结窗口里（窗口前还没报工，或者没排过）的批次整批不冻结、照常重排，
            # 由调用方事先提醒；窗口内读到的行本身没有坏，不整次拒绝。
            freeze_meta.setdefault("freeze_skipped_batch_ids", []).append(bid)
            continue

        _cache_seed_for_prefix(prefix=prefix, schedule_map=schedule_map, op_by_id=scope.op_by_id,
                               seed_tmp=seed_tmp, point_validator=point_validator)

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
        # 一个前缀都没冻住（如前道原安排不在冻结窗口里的批次全被跳过），补上 reason，保住"disabled 必带可查原因"的诊断口径。
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_FREEZABLE_PREFIX)
    _set_freeze_applied(freeze_meta, frozen_op_ids)
    return frozen_op_ids, seed_results


def build_freeze_window_seed(
    *,
    prev_version: int,
    start_dt: datetime,
    reschedulable_operations: List[Any],
    meta: Dict[str, Any],
    point_validator: Any,
    schedule_rows_reader: Any,
    hold_window: Optional[Tuple[datetime, datetime]] = None,
) -> Tuple[Set[int], List[Dict[str, Any]]]:
    """上一版计划在不重排时段里要原样保留的原安排；零工时原安排的依据由 point_validator 核对，对不上即拒绝。

    前道原安排不在窗口里的批次不冻结、记进 meta["freeze_skipped_batch_ids"]。
    hold_window=(开始, 结束) 时：和这段时间重叠的原安排保留，同批次排在前面的
    从 start_dt 起读到的原安排一起保留；记进 meta["hold_window"]。为 None 时不保留。
    """
    freeze_meta = _init_freeze_meta(meta)

    scope = _prepare_freeze_seed_scope(
        prev_version=int(prev_version),
        start_dt=start_dt,
        seed_operations=reschedulable_operations,
        freeze_meta=freeze_meta,
        hold_window=hold_window,
    )
    if scope is None:
        return _empty_freeze_seed_result(freeze_meta)

    schedule_map = _load_previous_schedule_for_freeze(
        scope=scope,
        prev_version=int(prev_version),
        freeze_meta=freeze_meta,
        schedule_rows_reader=schedule_rows_reader,
    )
    if schedule_map is None:
        return _empty_freeze_seed_result(freeze_meta)

    seed_tmp: Dict[int, Dict[str, Any]] = {}
    frozen_op_ids = _apply_freeze_prefixes(
        scope=scope,
        schedule_map=schedule_map,
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
