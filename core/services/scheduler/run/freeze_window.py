from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithms.value_domains import INTERNAL
from core.infrastructure.errors import ValidationError
from core.models.enums import YesNo

from ..number_utils import to_yes_no

_FREEZE_DEGRADATION_CODE = "freeze_seed_unavailable"


@dataclass(frozen=True)
class _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]]
    invalid_row_count: int
    invalid_row_samples: List[str]


def _init_freeze_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = meta if isinstance(meta, dict) else {}
    out.setdefault("freeze_state", "disabled")
    out.setdefault("freeze_applied", False)
    out.setdefault("freeze_degradation_codes", [])
    out.setdefault("freeze_enabled", False)
    out.setdefault("freeze_days", 0)
    out.setdefault("freeze_degradation_reason", None)
    return out


def _freeze_window_days(cfg: Any, prev_version: int, *, strict_mode: bool, meta: Dict[str, Any], warnings: List[str]) -> int:
    enabled = to_yes_no(cfg.freeze_window_enabled, default=YesNo.NO.value) == YesNo.YES.value
    meta["freeze_enabled"] = bool(enabled)
    if not enabled:
        meta["freeze_state"] = "disabled"
        meta["freeze_days"] = 0
        return 0

    cfg_events = list(getattr(cfg, "degradation_events", ()) or ())
    cfg_degraded = any(
        str(event.get("field") or "") == "freeze_window_days" or str(event.get("code") or "") == _FREEZE_DEGRADATION_CODE
        for event in cfg_events
        if isinstance(event, dict)
    )
    days = int(cfg.freeze_window_days or 0)
    meta["freeze_days"] = int(days)

    if cfg_degraded:
        _record_freeze_degradation(
            meta,
            warnings,
            "freeze window config degraded; treating as disabled",
            strict_mode=strict_mode,
        )
        return 0
    if days <= 0:
        meta["freeze_state"] = "disabled"
        return 0
    if int(prev_version or 0) <= 0:
        meta["freeze_state"] = "disabled"
        return 0
    return int(days)


def _record_freeze_degradation(
    meta: Dict[str, Any],
    warnings: List[str],
    message: str,
    *,
    strict_mode: bool,
) -> None:
    meta["freeze_state"] = "degraded"
    codes = [str(code).strip() for code in list(meta.get("freeze_degradation_codes") or []) if str(code).strip()]
    if _FREEZE_DEGRADATION_CODE not in codes:
        codes.append(_FREEZE_DEGRADATION_CODE)
    meta["freeze_degradation_codes"] = codes
    meta["freeze_degradation_reason"] = str(message)
    if strict_mode:
        raise ValidationError(f"freeze window degraded: {message}", field="freeze_window")
    warnings.append(f"[freeze_window] {message}")


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
) -> _LoadedScheduleMapOutcome:
    schedule_map: Dict[int, Dict[str, Any]] = {}
    invalid_row_count = 0
    invalid_row_samples: List[str] = []
    rows = svc.schedule_repo.list_version_rows_by_op_ids_start_range(
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


def _max_seq_by_batch(schedule_map: Dict[int, Dict[str, Any]], op_by_id: Dict[int, Any]) -> Dict[str, int]:
    max_seq_by_batch: Dict[str, int] = {}
    for oid in schedule_map.keys():
        op0 = op_by_id.get(int(oid))
        if not op0:
            continue
        bid = str(op0.batch_id or "")
        seq0 = int(op0.seq or 0)
        if seq0 <= 0:
            continue
        max_seq_by_batch[bid] = max(max_seq_by_batch.get(bid, 0), seq0)
    return max_seq_by_batch


def _prefix_op_ids_for_batch(operations: List[Any], bid: str, max_seq: int) -> List[int]:
    return [int(op.id) for op in operations if op and op.id and op.batch_id == bid and int(op.seq or 0) <= max_seq]


def _cache_seed_for_prefix(
    svc,
    *,
    prefix: List[int],
    schedule_map: Dict[int, Dict[str, Any]],
    seed_tmp: Dict[int, Dict[str, Any]],
) -> int:
    for oid in prefix:
        row = schedule_map.get(int(oid)) or {}
        st = svc._normalize_datetime(row.get("start_time"))
        et = svc._normalize_datetime(row.get("end_time"))
        if not st or not et or et <= st:
            return int(oid)
        seed_tmp[int(oid)] = {"row": row, "start_time": st, "end_time": et}
    return 0


def _discard_seed_cache(prefix: List[int], seed_tmp: Dict[int, Dict[str, Any]]) -> None:
    for oid in prefix:
        seed_tmp.pop(int(oid), None)


def _build_seed_results(
    frozen_op_ids: Set[int],
    *,
    op_by_id: Dict[int, Any],
    seed_tmp: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seed_results: List[Dict[str, Any]] = []
    for oid in sorted(frozen_op_ids):
        op0 = op_by_id.get(oid)
        seed = seed_tmp.get(oid)
        if not op0 or not seed:
            continue
        row = seed.get("row")
        st = seed.get("start_time")
        et = seed.get("end_time")
        if not row or not st or not et:
            continue
        seed_results.append(
            {
                "op_id": oid,
                "op_code": op0.op_code,
                "batch_id": op0.batch_id,
                "seq": int(op0.seq or 0),
                "machine_id": row.get("machine_id"),
                "operator_id": row.get("operator_id"),
                "start_time": st,
                "end_time": et,
                "source": (op0.source or INTERNAL).strip(),
                "op_type_name": getattr(op0, "op_type_name", None),
            }
        )
    return seed_results


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
) -> Tuple[Set[int], List[Dict[str, Any]], List[str]]:
    frozen_op_ids: Set[int] = set()
    seed_results: List[Dict[str, Any]] = []
    warnings: List[str] = []
    freeze_meta = _init_freeze_meta(meta)

    freeze_days = _freeze_window_days(
        cfg,
        prev_version,
        strict_mode=bool(strict_mode),
        meta=freeze_meta,
        warnings=warnings,
    )
    if freeze_days <= 0:
        freeze_meta["freeze_applied"] = False
        return frozen_op_ids, seed_results, warnings

    freeze_end = start_dt + timedelta(days=freeze_days)
    freeze_end_str = svc._format_dt(freeze_end)
    start_str = svc._format_dt(start_dt)

    seed_operations = reschedulable_operations if reschedulable_operations is not None else operations
    op_by_id: Dict[int, Any] = {int(op.id): op for op in seed_operations if op and op.id}
    op_ids_all = sorted(list(op_by_id.keys()))
    if not op_ids_all:
        freeze_meta["freeze_applied"] = False
        return frozen_op_ids, seed_results, warnings

    try:
        load_outcome = _load_schedule_map(
            svc,
            prev_version=int(prev_version),
            op_ids=op_ids_all,
            start_str=start_str,
            freeze_end_str=freeze_end_str,
        )
    except Exception as exc:
        _record_freeze_degradation(
            freeze_meta,
            warnings,
            f"failed to load previous schedule rows: {exc}",
            strict_mode=bool(strict_mode),
        )
        freeze_meta["freeze_applied"] = False
        return frozen_op_ids, seed_results, warnings

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
            freeze_meta["freeze_applied"] = False
            return frozen_op_ids, seed_results, warnings

    schedule_map = load_outcome.schedule_map
    if not schedule_map:
        freeze_meta["freeze_applied"] = False
        return frozen_op_ids, seed_results, warnings

    seed_tmp: Dict[int, Dict[str, Any]] = {}
    max_seq_by_batch = _max_seq_by_batch(schedule_map, op_by_id)

    for bid, max_seq in max_seq_by_batch.items():
        if max_seq <= 0:
            continue
        prefix = _prefix_op_ids_for_batch(seed_operations, bid, max_seq)
        missing = [oid for oid in prefix if oid not in schedule_map]
        if missing:
            sample = ", ".join([str(x) for x in missing[:5]])
            _record_freeze_degradation(
                freeze_meta,
                warnings,
                f"missing prefix rows for batch {bid}: {sample}",
                strict_mode=bool(strict_mode),
            )
            continue

        invalid_oid = _cache_seed_for_prefix(svc, prefix=prefix, schedule_map=schedule_map, seed_tmp=seed_tmp)
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

    seed_results = _build_seed_results(frozen_op_ids, op_by_id=op_by_id, seed_tmp=seed_tmp)
    seed_results.sort(key=lambda x: (x.get("start_time") or datetime.min, x.get("op_id") or 0))

    freeze_meta["freeze_applied"] = bool(frozen_op_ids)
    if str(freeze_meta.get("freeze_state") or "").strip().lower() != "degraded":
        freeze_meta["freeze_state"] = "active" if frozen_op_ids else "disabled"
    return frozen_op_ids, seed_results, warnings
