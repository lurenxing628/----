from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult, point_seed_valid
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.algo_stats import increment_counter
from core.infrastructure.errors import ValidationError


class _SeedScheduleResult(ScheduleResult):
    # Internal transport only: not a dataclass field or part of the public result schema.
    __slots__ = ("_external_group_identity",)

    def __init__(self, result: ScheduleResult, identity: Tuple[int, str, str, Optional[str]]) -> None:
        super().__init__(**asdict(result))
        self._external_group_identity = identity


def with_seed_external_group_metadata(result: ScheduleResult, metadata: Any) -> ScheduleResult:
    if not isinstance(metadata, dict) or set(metadata) not in (
        {"op_id", "batch_id", "ext_group_id"}, {"op_id", "batch_id", "ext_group_id", "piece_id"},
    ):
        raise ValidationError("冻结外协种子的组身份资料不完整，系统已停止排产。", field="seed_results")
    op_id = _identity_int(metadata["op_id"])
    batch_id, group_id = metadata["batch_id"], metadata["ext_group_id"]
    if op_id <= 0 or not all(isinstance(value, str) and value.strip() for value in (batch_id, group_id)):
        raise ValidationError("冻结外协种子的组身份资料无效，系统已停止排产。", field="seed_results")
    piece = metadata.get("piece_id")
    if "piece_id" in metadata and (type(piece) is not str or not piece or piece.strip() != piece):
        raise ValidationError("Frozen piece identity must be canonical.", field="seed_results")
    seed = _SeedScheduleResult(result, (op_id, batch_id.strip(), group_id.strip(), piece))
    seed_external_group_key(seed)
    return seed


def seed_external_group_key(result: ScheduleResult) -> Optional[Tuple[str, ...]]:
    if not isinstance(result, _SeedScheduleResult):
        return None
    op_id, batch_id, group_id, piece = result._external_group_identity
    if (
        _identity_int(result.op_id) != op_id
        or str(result.batch_id or "").strip() != batch_id
        or str(result.source or "").strip().lower() != EXTERNAL
    ):
        raise ValidationError("冻结外协种子的组身份与工序不一致，系统已停止排产。", field="seed_results")
    key = batch_id, group_id
    return key if piece is None else key + (piece,)


def seed_external_group_keys(seed_results: List[ScheduleResult]) -> Dict[int, Tuple[str, ...]]:
    keys = {}
    for result in seed_results:
        key = seed_external_group_key(result)
        if key is not None:
            keys[_identity_int(result.op_id)] = key
    return keys


def seed_result_for_output(result: ScheduleResult) -> ScheduleResult:
    if isinstance(result, (_SeedScheduleResult, PointSeedResult)):
        return ScheduleResult(**asdict(result))
    return result


def normalize_seed_results(
    *,
    seed_results: Optional[List[ScheduleResult]],
    operations: List[Any],
    algo_stats: Any = None,
) -> Tuple[List[ScheduleResult], Set[int], List[str]]:
    warnings: List[str] = []
    seed_op_ids: Set[int] = set()
    if not seed_results:
        return [], seed_op_ids, warnings

    lookup = _build_operation_lookup(operations)
    counters = {
        "backfilled": 0,
        "dropped_invalid": 0,
        "dropped_bad_time_type": 0,
        "dropped_bad_time_order": 0,
        "dropped_bad_time_incomparable": 0,
        "dropped_dup": 0,
    }
    dup_samples: List[str] = []
    normalized: List[ScheduleResult] = []

    for seed_result in seed_results:
        original_oid = _identity_int(getattr(seed_result, "op_id", 0))
        result, reason = _normalize_one_seed_result(seed_result, lookup=lookup)
        if reason:
            counters[reason] += 1
            continue
        if result is None:
            continue
        oid = _identity_int(getattr(result, "op_id", 0))
        if oid <= 0:
            counters["dropped_invalid"] += 1
            continue
        if oid in seed_op_ids:
            counters["dropped_dup"] += 1
            if len(dup_samples) < 5:
                dup_samples.append(str(oid))
            continue
        if original_oid <= 0:
            counters["backfilled"] += 1
        seed_op_ids.add(oid)
        normalized.append(result)

    _record_seed_counters(algo_stats, counters)
    warnings.extend(_seed_warnings(counters, dup_samples))
    return normalized, seed_op_ids, warnings


def _build_operation_lookup(operations: List[Any]) -> Dict[str, Any]:
    op_id_by_code: Dict[str, int] = {}
    by_batch_seq: Dict[Tuple[str, int], int] = {}
    duplicates: set = set()
    for op in operations:
        oid = _identity_int(getattr(op, "id", 0))
        if oid <= 0:
            continue
        code = str(getattr(op, "op_code", "") or "").strip()
        if code and code not in op_id_by_code:
            op_id_by_code[code] = oid
        key = _batch_seq_key(op)
        if key is None:
            continue
        prev = by_batch_seq.get(key)
        if prev is not None and prev != oid:
            duplicates.add(key)
        else:
            by_batch_seq[key] = oid
    for key in duplicates:
        by_batch_seq.pop(key, None)
    return {"op_id_by_code": op_id_by_code, "op_id_by_batch_seq": by_batch_seq}


def _normalize_one_seed_result(seed_result: Any, *, lookup: Dict[str, Any]) -> Tuple[Optional[ScheduleResult], Optional[str]]:
    if not seed_result or getattr(seed_result, "start_time", None) is None or getattr(seed_result, "end_time", None) is None:
        return None, None
    invalid_time_reason = _invalid_time_window_reason(seed_result)
    if invalid_time_reason:
        return None, invalid_time_reason

    raw_oid = getattr(seed_result, "op_id", 0)
    oid = _identity_int(raw_oid)
    if _invalid_identity_supplied(getattr(seed_result, "seq", 0)):
        return None, "dropped_invalid"
    if oid > 0:
        return seed_result, None
    if _invalid_identity_supplied(raw_oid):
        return None, "dropped_invalid"
    new_oid = _resolve_seed_op_id(seed_result, lookup=lookup)
    if new_oid <= 0:
        return None, "dropped_invalid"
    return _backfill_seed_op_id(seed_result, new_oid), None


def _invalid_time_window_reason(seed_result: Any) -> Optional[str]:
    if not isinstance(getattr(seed_result, "start_time", None), datetime) or not isinstance(getattr(seed_result, "end_time", None), datetime):
        return "dropped_bad_time_type"
    try:
        if seed_result.end_time > seed_result.start_time:
            return None
        if point_seed_valid(seed_result):
            return None
    except TypeError:
        return "dropped_bad_time_incomparable"
    return "dropped_bad_time_order"


def _resolve_seed_op_id(seed_result: Any, *, lookup: Dict[str, Any]) -> int:
    code = str(getattr(seed_result, "op_code", "") or "").strip()
    if code:
        return int(lookup["op_id_by_code"].get(code, 0) or 0)
    key = _batch_seq_key(seed_result)
    if key is None:
        return 0
    return int(lookup["op_id_by_batch_seq"].get(key, 0) or 0)


def _backfill_seed_op_id(seed_result: ScheduleResult, op_id: int) -> ScheduleResult:
    seed_result.op_id = int(op_id)
    return seed_result


def _batch_seq_key(obj: Any) -> Optional[Tuple[str, int]]:
    bid = str(getattr(obj, "batch_id", "") or "").strip()
    seq = _identity_int(getattr(obj, "seq", 0))
    return (bid, seq) if bid and seq > 0 else None


def _identity_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else 0
    text = str(value).strip()
    if not text:
        return 0
    digits = text[1:] if text[:1] in {"+", "-"} else text
    if not digits.isdecimal():
        return 0
    return int(text)


def _invalid_identity_supplied(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return value < 0
    if isinstance(value, float):
        return value < 0 or not value.is_integer()
    text = str(value).strip()
    if not text:
        return False
    if text.startswith("-"):
        return True
    digits = text[1:] if text[:1] in {"+", "-"} else text
    return not digits.isdecimal()


def _record_seed_counters(algo_stats: Any, counters: Dict[str, int]) -> None:
    bad_time_total = counters["dropped_bad_time_type"] + counters["dropped_bad_time_order"] + counters["dropped_bad_time_incomparable"]
    increment_counter(algo_stats, "seed_op_id_backfilled_count", counters["backfilled"])
    increment_counter(algo_stats, "seed_invalid_dropped_count", counters["dropped_invalid"])
    increment_counter(algo_stats, "seed_bad_time_dropped_count", bad_time_total)
    increment_counter(algo_stats, "seed_bad_time_type_dropped_count", counters["dropped_bad_time_type"])
    increment_counter(algo_stats, "seed_bad_time_order_dropped_count", counters["dropped_bad_time_order"])
    increment_counter(algo_stats, "seed_bad_time_incomparable_dropped_count", counters["dropped_bad_time_incomparable"])
    increment_counter(algo_stats, "seed_duplicate_dropped_count", counters["dropped_dup"])


def _seed_warnings(counters: Dict[str, int], dup_samples: List[str]) -> List[str]:
    warnings: List[str] = []
    if counters["backfilled"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['backfilled']} 条工序编号缺失或不合法的记录，已按工序代码、批次号和工序号补回工序编号，避免重复排产。")
    if counters["dropped_invalid"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['dropped_invalid']} 条工序编号缺失或不合法且无法匹配的记录，系统已忽略这些记录，避免重复统计或重复排产。")
    if counters["dropped_bad_time_type"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['dropped_bad_time_type']} 条开始时间或结束时间格式不正确的记录，系统已忽略这些记录，避免锁定近期排程或资源占用异常。")
    if counters["dropped_bad_time_order"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['dropped_bad_time_order']} 条开始时间不早于结束时间的记录，系统已忽略这些记录，避免锁定近期排程或资源占用异常。")
    if counters["dropped_bad_time_incomparable"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['dropped_bad_time_incomparable']} 条时间无法比较的记录，系统已忽略这些记录，避免锁定近期排程或资源占用异常。")
    if counters["dropped_dup"]:
        sample = ", ".join([x for x in dup_samples if x][:5])
        warnings.append(
            f"沿用旧排产结果时发现 {counters['dropped_dup']} 条重复工序编号的记录，已按工序编号去重（保留首条）"
            f"{('（示例工序编号：' + sample + '）') if sample else ''}。"
        )
    return warnings
