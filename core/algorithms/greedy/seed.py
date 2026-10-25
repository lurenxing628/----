from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.algo_stats import increment_counter
from core.errors import ValidationError

_RESULT_FIELDS = tuple(f.name for f in fields(ScheduleResult))


class _SeedScheduleResult(ScheduleResult):
    # Internal transport only: not a dataclass field or part of the public result schema.
    __slots__ = ("_external_group_identity", "_resource_segments")

    def __init__(self, result: ScheduleResult, identity: Optional[Tuple[int, str, str, Optional[str]]] = None,
                 segments: Any = None) -> None:
        super().__init__(**{name: getattr(result, name) for name in _RESULT_FIELDS})
        self._external_group_identity = identity
        self._resource_segments = segments


def with_seed_external_group_metadata(result: ScheduleResult, metadata: Any) -> ScheduleResult:
    if not isinstance(metadata, dict) or set(metadata) not in (
        {"op_id", "batch_id", "ext_group_id"}, {"op_id", "batch_id", "ext_group_id", "piece_id"},
    ):
        raise ValidationError("冻结外协种子的组身份资料不完整，系统已停止排产。", field="seed_results")
    op_id = identity_int(metadata["op_id"])
    batch_id, group_id = metadata["batch_id"], metadata["ext_group_id"]
    if op_id <= 0 or not all(isinstance(value, str) and value.strip() for value in (batch_id, group_id)):
        raise ValidationError("冻结外协种子的组身份资料无效，系统已停止排产。", field="seed_results")
    piece = metadata.get("piece_id")
    if "piece_id" in metadata and (type(piece) is not str or not piece or piece.strip() != piece):
        raise ValidationError("Frozen piece identity must be canonical.", field="seed_results")
    seed = _SeedScheduleResult(result, (op_id, batch_id.strip(), group_id.strip(), piece),
                               seed_resource_segments(result))
    seed_external_group_key(seed)
    return seed


def seed_external_group_key(result: ScheduleResult) -> Optional[Tuple[str, ...]]:
    if not isinstance(result, _SeedScheduleResult) or result._external_group_identity is None:
        return None
    op_id, batch_id, group_id, piece = result._external_group_identity
    if identity_int(result.op_id) != op_id or result.batch_id != batch_id or result.source != EXTERNAL:
        raise ValidationError("冻结外协种子的组身份与工序不一致，系统已停止排产。", field="seed_results")
    key = batch_id, group_id
    return key if piece is None else key + (piece,)


def with_seed_resource_segments(result: ScheduleResult, segments: Any) -> ScheduleResult:
    identity = result._external_group_identity if isinstance(result, _SeedScheduleResult) else None
    return _SeedScheduleResult(result, identity, segments)


def seed_resource_segments(result: ScheduleResult) -> Any:
    return result._resource_segments if isinstance(result, _SeedScheduleResult) else None


def seed_external_group_keys(seed_results: List[ScheduleResult]) -> Dict[int, Tuple[str, ...]]:
    keys = {}
    for result in seed_results:
        key = seed_external_group_key(result)
        if key is not None:
            keys[identity_int(result.op_id)] = key
    return keys


def seed_result_for_output(result: ScheduleResult) -> ScheduleResult:
    if isinstance(result, (_SeedScheduleResult, PointSeedResult)):
        return ScheduleResult(**{name: getattr(result, name) for name in _RESULT_FIELDS})
    return result


def normalize_seed_results(
    *,
    seed_results: Optional[List[ScheduleResult]],
    operations: List[OpForScheduleAlgo],
    algo_stats: Any = None,
) -> Tuple[List[ScheduleResult], Set[int], List[str]]:
    warnings: List[str] = []
    seed_op_ids: Set[int] = set()
    if not seed_results:
        return [], seed_op_ids, warnings

    lookup = (_build_operation_lookup(operations)
              if any(identity_int(result.op_id) <= 0 for result in seed_results) else {})
    counters = {
        "backfilled": 0,
        "dropped_invalid": 0,
        "dropped_dup": 0,
    }
    dup_samples: List[str] = []
    normalized: List[ScheduleResult] = []

    for seed_result in seed_results:
        original_oid = identity_int(seed_result.op_id)
        normalized_one = _normalize_one_seed_result(seed_result, original_oid=original_oid, lookup=lookup)
        if normalized_one is None:
            counters["dropped_invalid"] += 1
            continue
        result, oid = normalized_one
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


def _build_operation_lookup(operations: List[OpForScheduleAlgo]) -> Dict[str, Any]:
    op_id_by_code: Dict[str, int] = {}
    by_batch_seq: Dict[Tuple[str, int], int] = {}
    duplicates: set = set()
    for op in operations:
        # 工序编号、工序代码、批次号、工序号都由排产输入构建给出规范非空值。
        oid = op.id
        if op.op_code not in op_id_by_code:
            op_id_by_code[op.op_code] = oid
        key = (op.batch_id, op.seq)
        prev = by_batch_seq.get(key)
        if prev is not None and prev != oid:
            duplicates.add(key)
        else:
            by_batch_seq[key] = oid
    for key in duplicates:
        by_batch_seq.pop(key, None)
    return {"op_id_by_code": op_id_by_code, "op_id_by_batch_seq": by_batch_seq}


def _normalize_one_seed_result(
    seed_result: ScheduleResult, *, original_oid: int, lookup: Dict[str, Any],
) -> Optional[Tuple[ScheduleResult, int]]:
    # 起止时间与工序编号/工序号的取值都已在唯一入口 coerce_seed_results 校验并拒绝（身份转成非负整数），
    # 这里只按工序代码或批次号+工序号回填缺失的工序编号。
    if original_oid > 0:
        return seed_result, original_oid
    new_oid = _resolve_seed_op_id(seed_result, lookup=lookup)
    if new_oid <= 0:
        return None
    return _backfill_seed_op_id(seed_result, new_oid), new_oid


def _resolve_seed_op_id(seed_result: ScheduleResult, *, lookup: Dict[str, Any]) -> int:
    # 旧种子回填：存储边界可能给出空串或带空白的工序代码/批次号，只按已有资料匹配。
    code = seed_result.op_code.strip()
    if code:
        return lookup["op_id_by_code"].get(code, 0)
    bid, seq = seed_result.batch_id.strip(), identity_int(seed_result.seq)
    if not bid or seq <= 0:
        return 0
    return lookup["op_id_by_batch_seq"].get((bid, seq), 0)


def _backfill_seed_op_id(seed_result: ScheduleResult, op_id: int) -> ScheduleResult:
    seed_result.op_id = op_id
    return seed_result


def identity_int(value: Any) -> int:
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


def _record_seed_counters(algo_stats: Any, counters: Dict[str, int]) -> None:
    increment_counter(algo_stats, "seed_op_id_backfilled_count", counters["backfilled"])
    increment_counter(algo_stats, "seed_invalid_dropped_count", counters["dropped_invalid"])
    increment_counter(algo_stats, "seed_duplicate_dropped_count", counters["dropped_dup"])


def _seed_warnings(counters: Dict[str, int], dup_samples: List[str]) -> List[str]:
    warnings: List[str] = []
    if counters["backfilled"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['backfilled']} 条工序编号缺失或不合法的记录，已按工序代码、批次号和工序号补回工序编号，避免重复排产。")
    if counters["dropped_invalid"]:
        warnings.append(f"沿用旧排产结果时发现 {counters['dropped_invalid']} 条工序编号缺失或不合法且无法匹配的记录，系统已忽略这些记录，避免重复统计或重复排产。")
    if counters["dropped_dup"]:
        sample = ", ".join([x for x in dup_samples if x][:5])
        warnings.append(
            f"沿用旧排产结果时发现 {counters['dropped_dup']} 条重复工序编号的记录，已按工序编号去重（保留首条）"
            f"{('（示例工序编号：' + sample + '）') if sample else ''}。"
        )
    return warnings
