from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.errors import ValidationError
from core.models.enums import YesNo
from core.models.scheduler_degradation_messages import (
    FREEZE_WINDOW_DEGRADED_MESSAGE,
    FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
)
from core.shared.boolean_normalize import to_yes_no

from .freeze_window_prefixes import (
    group_seed_operations_by_batch,
    max_seq_by_batch,
    prefix_op_ids_for_batch,
    rows_in_window,
)
from .freeze_window_seed_rows import (
    build_seed_results as _build_seed_results,
)
from .freeze_window_seed_rows import (
    cache_seed_for_prefix as _cache_seed_for_prefix,
)
from .freeze_window_seed_rows import (
    discard_seed_cache as _discard_seed_cache,
)

_FREEZE_DEGRADATION_CODE = "freeze_seed_unavailable"
_FREEZE_CONFIG_FIELDS = {"freeze_window_enabled", "freeze_window_days"}
_FREEZE_DISABLED_CONFIG_DISABLED = "config_disabled"
_FREEZE_DISABLED_NO_DAYS = "no_days"
_FREEZE_DISABLED_NO_PREVIOUS_VERSION = "no_previous_version"
_FREEZE_DISABLED_CONFIG_DEGRADED = "config_degraded"
_FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS = "no_reschedulable_operations"
_FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS = "no_previous_schedule_rows"
_FREEZE_DISABLED_NO_FREEZABLE_PREFIX = "no_freezable_prefix"


@dataclass(frozen=True)
class _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]]
    invalid_row_count: int
    invalid_row_samples: List[str]


@dataclass(frozen=True)
class _FreezeSeedScope:
    freeze_days: int
    start_str: str
    freeze_end_str: str
    seed_operations: List[Any]
    seed_operations_by_batch: Dict[str, List[Any]]
    op_by_id: Dict[int, Any]
    op_ids_all: List[int]
    # 调用方指定的时段：只有和 [anchor_start, anchor_end) 重叠的原安排算"要保留"，同批次前道从 start_str 起补齐。
    # 为 None 时沿用旧口径：读到的窗口内原安排都算。
    anchor_start: Optional[datetime] = None
    anchor_end: Optional[datetime] = None


def _init_freeze_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = meta if isinstance(meta, dict) else {}
    out.setdefault("freeze_state", "disabled")
    out.setdefault("freeze_applied", False)
    out.setdefault("freeze_application_status", None)
    out.setdefault("freeze_degradation_codes", [])
    out.setdefault("freeze_enabled", False)
    out.setdefault("freeze_days", 0)
    out.setdefault("freeze_degradation_reason", None)
    out.setdefault("freeze_degradation_count", 0)
    out.setdefault("freeze_disabled_reason", None)
    return out


def _freeze_config_degraded(cfg: Any) -> bool:
    for event in list(getattr(cfg, "degradation_events", ()) or ()):
        if not isinstance(event, dict):
            continue
        field = str(event.get("field") or "").strip()
        code = str(event.get("code") or "").strip()
        if field in _FREEZE_CONFIG_FIELDS or code == _FREEZE_DEGRADATION_CODE:
            return True
    return False


def _set_freeze_disabled(meta: Dict[str, Any], reason: str) -> None:
    meta["freeze_state"] = "disabled"
    meta["freeze_disabled_reason"] = reason


def _freeze_window_days(
    cfg: Any, prev_version: int, *, strict_mode: bool, meta: Dict[str, Any], warnings: List[str]
) -> int:
    cfg_degraded = _freeze_config_degraded(cfg)
    enabled = to_yes_no(cfg.freeze_window_enabled, default=YesNo.NO.value) == YesNo.YES.value
    meta["freeze_enabled"] = bool(enabled)
    days = int(cfg.freeze_window_days or 0)
    meta["freeze_days"] = int(days)

    if cfg_degraded:
        _record_freeze_degradation(
            meta,
            warnings,
            "freeze window config degraded",
            strict_mode=strict_mode,
            disabled_reason=_FREEZE_DISABLED_CONFIG_DEGRADED,
        )
        return 0
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


def _record_freeze_degradation(
    meta: Dict[str, Any],
    warnings: List[str],
    message: str,
    *,
    strict_mode: bool,
    disabled_reason: Optional[str] = None,
) -> None:
    meta["freeze_state"] = "degraded"
    meta["freeze_disabled_reason"] = disabled_reason
    codes = [str(code).strip() for code in list(meta.get("freeze_degradation_codes") or []) if str(code).strip()]
    if _FREEZE_DEGRADATION_CODE not in codes:
        codes.append(_FREEZE_DEGRADATION_CODE)
    meta["freeze_degradation_codes"] = codes
    meta["freeze_degradation_reason"] = FREEZE_WINDOW_DEGRADED_MESSAGE
    meta["freeze_degradation_count"] = int(meta.get("freeze_degradation_count") or 0) + 1
    if strict_mode:
        raise ValidationError(FREEZE_WINDOW_DEGRADED_MESSAGE, field="freeze_window")
    warnings.append(f"[freeze_window] {FREEZE_WINDOW_DEGRADED_MESSAGE}")


def _finalize_freeze_application_status(meta: Dict[str, Any]) -> None:
    if str(meta.get("freeze_state") or "").strip().lower() != "degraded":
        if bool(meta.get("freeze_applied")):
            meta["freeze_application_status"] = "applied"
        else:
            meta["freeze_application_status"] = None
        return

    if bool(meta.get("freeze_applied")):
        meta["freeze_application_status"] = "partially_applied"
        meta["freeze_degradation_public_code"] = "freeze_window_partially_applied"
        meta["freeze_degradation_reason"] = FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE
        return

    meta["freeze_application_status"] = "unapplied"
    meta["freeze_degradation_public_code"] = "freeze_window_unapplied"
    meta["freeze_degradation_reason"] = FREEZE_WINDOW_DEGRADED_MESSAGE


def _invalid_schedule_row_sample(row: Any) -> str:
    try:
        row_dict = dict(row)
    except Exception:
        row_dict = {"repr": repr(row)[:160]}
    parts: List[str] = []
    for key in ("op_id", "start_time", "end_time"):
        value = row_dict.get(key)
        if value in (None, ""):
            continue
        parts.append(f"{key}={value}")
    return ",".join(parts) or repr(row_dict)[:160]


def _load_schedule_map(
    svc,
    *,
    prev_version: int,
    op_ids: List[int],
    start_str: str,
    freeze_end_str: str,
    schedule_rows_reader: Any = None,
) -> _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]] = {}
    invalid_row_count = 0
    invalid_row_samples: List[str] = []
    duplicate_op_ids: Set[int] = set()
    reader = schedule_rows_reader if schedule_rows_reader is not None else svc.schedule_repo.list_version_rows_by_op_ids_start_range
    rows = reader(
        version=int(prev_version),
        op_ids=op_ids,
        start_time=start_str,
        end_time=freeze_end_str,
    )
    for row in rows:
        try:
            row_dict = dict(row)
            oid = int(row_dict.get("op_id") or 0)
            if oid <= 0:
                raise ValueError("op_id must be positive")
            if oid in schedule_map or oid in duplicate_op_ids:
                duplicate_op_ids.add(int(oid))
                schedule_map.pop(int(oid), None)
                invalid_row_count += 1
                if len(invalid_row_samples) < 5:
                    invalid_row_samples.append(f"duplicate op_id={oid}")
                continue
            schedule_map[int(oid)] = row_dict
        except Exception:
            invalid_row_count += 1
            if len(invalid_row_samples) < 5:
                invalid_row_samples.append(_invalid_schedule_row_sample(row))
    return _LoadedScheduleMapOutcome(
        schedule_map=schedule_map,
        invalid_row_count=int(invalid_row_count),
        invalid_row_samples=invalid_row_samples,
    )


def _empty_freeze_seed_result(
    freeze_meta: Dict[str, Any],
    warnings: List[str],
) -> Tuple[Set[int], List[Dict[str, Any]], List[str]]:
    freeze_meta["freeze_applied"] = False
    _finalize_freeze_application_status(freeze_meta)
    return set(), [], warnings


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
    svc,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
    reschedulable_operations: Optional[List[Any]],
    strict_mode: bool,
    freeze_meta: Dict[str, Any],
    warnings: List[str],
    hold_window: Optional[Tuple[datetime, datetime]] = None,
) -> Optional[_FreezeSeedScope]:
    if hold_window is not None:
        freeze_days = _hold_window_days(hold_window, start_dt, prev_version, freeze_meta)
    else:
        freeze_days = _freeze_window_days(
            cfg,
            prev_version,
            strict_mode=bool(strict_mode),
            meta=freeze_meta,
            warnings=warnings,
        )
    if freeze_days <= 0:
        return None

    freeze_end = hold_window[1] if hold_window is not None else start_dt + timedelta(days=freeze_days)
    seed_operations = reschedulable_operations if reschedulable_operations is not None else operations
    seed_operations_by_batch = group_seed_operations_by_batch(seed_operations)
    op_by_id: Dict[int, Any] = {int(op.id): op for op in seed_operations if op and op.id}
    op_ids_all = sorted(list(op_by_id.keys()))
    if not op_ids_all:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_RESCHEDULABLE_OPERATIONS)
        return None

    return _FreezeSeedScope(
        freeze_days=int(freeze_days),
        start_str=svc._format_dt(start_dt),
        freeze_end_str=svc._format_dt(freeze_end),
        seed_operations=seed_operations,
        seed_operations_by_batch=seed_operations_by_batch,
        op_by_id=op_by_id,
        op_ids_all=op_ids_all,
        anchor_start=hold_window[0] if hold_window is not None else None,
        anchor_end=hold_window[1] if hold_window is not None else None,
    )


def _load_previous_schedule_for_freeze(
    svc,
    *,
    scope: _FreezeSeedScope,
    prev_version: int,
    strict_mode: bool,
    freeze_meta: Dict[str, Any],
    warnings: List[str],
    schedule_rows_reader: Any = None,
) -> Optional[_LoadedScheduleMapOutcome]:
    try:
        load_outcome = _load_schedule_map(
            svc,
            prev_version=int(prev_version),
            op_ids=scope.op_ids_all,
            start_str=scope.start_str,
            freeze_end_str=scope.freeze_end_str,
            schedule_rows_reader=schedule_rows_reader,
        )
    except Exception:
        logger = getattr(svc, "logger", None)
        if logger is not None:
            logger.exception("冻结窗口加载上一版本排程失败")
        _record_freeze_degradation(
            freeze_meta,
            warnings,
            FREEZE_WINDOW_DEGRADED_MESSAGE,
            strict_mode=bool(strict_mode),
        )
        return None

    if load_outcome.invalid_row_count > 0:
        sample_text = ", ".join(load_outcome.invalid_row_samples[:5])
        _record_freeze_degradation(
            freeze_meta,
            warnings,
            f"previous schedule rows contained {load_outcome.invalid_row_count} invalid entries"
            + (f" ({sample_text})" if sample_text else ""),
            strict_mode=bool(strict_mode),
        )
        if not load_outcome.schedule_map:
            return None

    if not load_outcome.schedule_map:
        _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_PREVIOUS_SCHEDULE_ROWS)
        return None

    return load_outcome


def _apply_freeze_prefixes(
    svc,
    *,
    scope: _FreezeSeedScope,
    schedule_map: Dict[int, Dict[str, Any]],
    seed_tmp: Dict[int, Dict[str, Any]],
    freeze_meta: Dict[str, Any],
    warnings: List[str],
    strict_mode: bool,
    point_validator: Any = None,
    skip_incomplete_prefix: bool = False,
) -> Set[int]:
    frozen_op_ids: Set[int] = set()
    max_seq_lookup = max_seq_by_batch(
        rows_in_window(svc, scope.anchor_start, scope.anchor_end, schedule_map), scope.op_by_id)

    for bid, max_seq in max_seq_lookup.items():
        if max_seq <= 0:
            continue
        prefix = prefix_op_ids_for_batch(scope.seed_operations_by_batch.get(bid, []), bid, max_seq)
        missing = [oid for oid in prefix if oid not in schedule_map]
        if missing and skip_incomplete_prefix:
            # 调用方明确接受：前道原安排不在冻结窗口里（窗口前还没报工，或者没排过）的批次整批不冻结、
            # 照常重排，由调用方事先提醒；窗口内读到的行本身没有坏，严格模式下也不整次拒绝。
            freeze_meta.setdefault("freeze_skipped_batch_ids", []).append(bid)
            continue
        if missing:
            sample = ", ".join([str(x) for x in missing[:5]])
            _record_freeze_degradation(
                freeze_meta,
                warnings,
                f"missing prefix rows for batch {bid}: {sample}",
                strict_mode=bool(strict_mode),
            )
            continue

        invalid_oid = _cache_seed_for_prefix(svc, prefix=prefix, schedule_map=schedule_map, seed_tmp=seed_tmp,
                                             point_validator=point_validator)
        if invalid_oid:
            _record_freeze_degradation(
                freeze_meta,
                warnings,
                f"invalid previous schedule time range for op_id={invalid_oid}",
                strict_mode=bool(strict_mode),
            )
            _discard_seed_cache(prefix, seed_tmp)
            continue

        for oid in prefix:
            frozen_op_ids.add(int(oid))

    return frozen_op_ids


def _finish_freeze_seed_result(
    frozen_op_ids: Set[int],
    *,
    scope: _FreezeSeedScope,
    seed_tmp: Dict[int, Dict[str, Any]],
    freeze_meta: Dict[str, Any],
    warnings: List[str],
) -> Tuple[Set[int], List[Dict[str, Any]], List[str]]:
    seed_results = _build_seed_results(frozen_op_ids, op_by_id=scope.op_by_id, seed_tmp=seed_tmp)
    seed_results.sort(key=lambda x: (x.get("start_time") or datetime.min, x.get("op_id") or 0))

    freeze_meta["freeze_applied"] = bool(frozen_op_ids)
    if str(freeze_meta.get("freeze_state") or "").strip().lower() != "degraded":
        if frozen_op_ids:
            freeze_meta["freeze_state"] = "active"
        else:
            # 走到收尾且非 degraded 但一个前缀都没冻住（如上一版窗内命中行全部对应
            # seq<=0 工序，被 freeze_window_prefixes.max_seq_by_batch 跳过）。补上
            # reason，保住"disabled 必带可查原因"的诊断口径（audit 2026-07-20 A15）。
            _set_freeze_disabled(freeze_meta, _FREEZE_DISABLED_NO_FREEZABLE_PREFIX)
    _finalize_freeze_application_status(freeze_meta)
    return frozen_op_ids, seed_results, warnings


def build_freeze_window_seed(
    svc,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
    reschedulable_operations: Optional[List[Any]] = None,
    strict_mode: bool = False,
    meta: Optional[Dict[str, Any]] = None,
    point_validator: Any = None,
    schedule_rows_reader: Any = None,
    skip_incomplete_prefix: bool = False,
    hold_window: Optional[Tuple[datetime, datetime]] = None,
) -> Tuple[Set[int], List[Dict[str, Any]], List[str]]:
    """skip_incomplete_prefix=True 时，前道原安排不在窗口里的批次不冻结、记进 meta["freeze_skipped_batch_ids"]。

    hold_window=(开始, 结束) 时不看配置里的冻结开关和天数：和这段时间重叠的原安排保留，同批次排在前面的
    从 start_dt 起读到的原安排一起保留；记进 meta["hold_window"]。为 None 时行为不变。
    """
    warnings: List[str] = []
    freeze_meta = _init_freeze_meta(meta)

    scope = _prepare_freeze_seed_scope(
        svc,
        cfg=cfg,
        prev_version=int(prev_version),
        start_dt=start_dt,
        operations=operations,
        reschedulable_operations=reschedulable_operations,
        strict_mode=bool(strict_mode),
        freeze_meta=freeze_meta,
        warnings=warnings,
        hold_window=hold_window,
    )
    if scope is None:
        return _empty_freeze_seed_result(freeze_meta, warnings)

    load_outcome = _load_previous_schedule_for_freeze(
        svc,
        scope=scope,
        prev_version=int(prev_version),
        strict_mode=bool(strict_mode),
        freeze_meta=freeze_meta,
        warnings=warnings,
        schedule_rows_reader=schedule_rows_reader,
    )
    if load_outcome is None:
        return _empty_freeze_seed_result(freeze_meta, warnings)

    seed_tmp: Dict[int, Dict[str, Any]] = {}
    frozen_op_ids = _apply_freeze_prefixes(
        svc,
        scope=scope,
        schedule_map=load_outcome.schedule_map,
        seed_tmp=seed_tmp,
        freeze_meta=freeze_meta,
        warnings=warnings,
        strict_mode=bool(strict_mode),
        point_validator=point_validator,
        skip_incomplete_prefix=bool(skip_incomplete_prefix),
    )
    return _finish_freeze_seed_result(
        frozen_op_ids,
        scope=scope,
        seed_tmp=seed_tmp,
        freeze_meta=freeze_meta,
        warnings=warnings,
    )
