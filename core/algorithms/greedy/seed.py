from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.algo_stats import increment_counter

_RESULT_FIELDS = tuple(f.name for f in fields(ScheduleResult))


class _SeedScheduleResult(ScheduleResult):
    # Internal transport only: not a dataclass field or part of the public result schema.
    __slots__ = ("_external_group_identity", "_resource_segments")

    def __init__(self, result: ScheduleResult, identity: Optional[Tuple[str, ...]] = None,
                 segments: Any = None) -> None:
        super().__init__(**{name: getattr(result, name) for name in _RESULT_FIELDS})
        self._external_group_identity = identity
        self._resource_segments = segments


def with_seed_external_group_metadata(result: ScheduleResult, metadata: Mapping[str, Any]) -> ScheduleResult:
    batch_id = metadata["batch_id"]
    group_id = metadata["ext_group_id"]
    piece = metadata.get("piece_id")
    identity: Tuple[str, ...] = (batch_id, group_id) if piece is None else (batch_id, group_id, piece)
    return _SeedScheduleResult(result, identity, seed_resource_segments(result))


def seed_external_group_key(result: ScheduleResult) -> Optional[Tuple[str, ...]]:
    return result._external_group_identity if isinstance(result, _SeedScheduleResult) else None


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
            keys[result.op_id] = key
    return keys


def seed_result_for_output(result: ScheduleResult) -> ScheduleResult:
    if isinstance(result, (_SeedScheduleResult, PointSeedResult)):
        return ScheduleResult(**{name: getattr(result, name) for name in _RESULT_FIELDS})
    return result


def normalize_seed_results(
    *,
    seed_results: List[ScheduleResult],
    algo_stats: Dict[str, Any],
) -> Tuple[List[ScheduleResult], Set[int], List[str]]:
    """Keep the first seed of each operation ID.

    Every seed already carries a positive operation ID: the evaluation context built before the
    decode session rejects seeds without one (``evaluation_completion._result_key``).
    """
    seed_op_ids: Set[int] = set()
    normalized: List[ScheduleResult] = []
    dup_samples: List[str] = []
    dropped_dup = 0
    for seed_result in seed_results:
        oid = seed_result.op_id
        if oid in seed_op_ids:
            dropped_dup += 1
            if len(dup_samples) < 5:
                dup_samples.append(str(oid))
            continue
        seed_op_ids.add(oid)
        normalized.append(seed_result)
    increment_counter(algo_stats, "seed_duplicate_dropped_count", dropped_dup)
    return normalized, seed_op_ids, _seed_warnings(dropped_dup, dup_samples)


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


def _seed_warnings(dropped_dup: int, dup_samples: List[str]) -> List[str]:
    if not dropped_dup:
        return []
    sample = ", ".join(dup_samples)
    return [
        f"沿用旧排产结果时发现 {dropped_dup} 条重复工序编号的记录，已按工序编号去重（保留首条）"
        f"{('（示例工序编号：' + sample + '）') if sample else ''}。"
    ]
