from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.algorithm_contracts.schedule_point_evidence import PointSeedResult
from core.algorithm_contracts.types import ScheduleResult

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
