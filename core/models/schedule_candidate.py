from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int
from .enums import LockStatus


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


@dataclass
class ScheduleCandidate:
    id: Optional[int]
    version: int
    candidate_key: str
    candidate_label: str
    candidate_kind: str
    status: str
    graph_enabled: str = "no"
    weight_level: Optional[int] = None
    weight_count: Optional[int] = None
    critical_weight: Optional[int] = None
    impact_weight: Optional[int] = None
    downstream_weight: Optional[int] = None
    sort_strategy: Optional[str] = None
    dispatch_mode: Optional[str] = None
    dispatch_rule: Optional[str] = None
    objective: Optional[str] = None
    score_json: Optional[str] = None
    metrics_json: Optional[str] = None
    health_json: Optional[str] = None
    summary_json: Optional[str] = None
    selection_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    detail_saved: str = "no"
    elapsed_ms: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleCandidate:
        return cls(
            id=parse_int(get(row, "id"), default=None),
            version=parse_int(get(row, "version"), default=0) or 0,
            candidate_key=str(get(row, "candidate_key") or ""),
            candidate_label=str(get(row, "candidate_label") or ""),
            candidate_kind=str(get(row, "candidate_kind") or ""),
            status=str(get(row, "status") or ""),
            graph_enabled=str(get(row, "graph_enabled") or "no"),
            weight_level=parse_int(get(row, "weight_level"), default=None),
            weight_count=parse_int(get(row, "weight_count"), default=None),
            critical_weight=parse_int(get(row, "critical_weight"), default=None),
            impact_weight=parse_int(get(row, "impact_weight"), default=None),
            downstream_weight=parse_int(get(row, "downstream_weight"), default=None),
            sort_strategy=_text_or_none(get(row, "sort_strategy")),
            dispatch_mode=_text_or_none(get(row, "dispatch_mode")),
            dispatch_rule=_text_or_none(get(row, "dispatch_rule")),
            objective=_text_or_none(get(row, "objective")),
            score_json=_text_or_none(get(row, "score_json")),
            metrics_json=_text_or_none(get(row, "metrics_json")),
            health_json=_text_or_none(get(row, "health_json")),
            summary_json=_text_or_none(get(row, "summary_json")),
            selection_reason=_text_or_none(get(row, "selection_reason")),
            failure_reason=_text_or_none(get(row, "failure_reason")),
            detail_saved=str(get(row, "detail_saved") or "no"),
            elapsed_ms=parse_int(get(row, "elapsed_ms"), default=None),
            started_at=_text_or_none(get(row, "started_at")),
            finished_at=_text_or_none(get(row, "finished_at")),
            created_at=_text_or_none(get(row, "created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)


@dataclass
class ScheduleCandidateRows:
    id: Optional[int]
    version: int
    candidate_id: int
    op_id: int
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    start_time: str = ""
    end_time: str = ""
    lock_status: str = LockStatus.UNLOCKED.value
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleCandidateRows:
        return cls(
            id=parse_int(get(row, "id"), default=None),
            version=parse_int(get(row, "version"), default=0) or 0,
            candidate_id=parse_int(get(row, "candidate_id"), default=0) or 0,
            op_id=parse_int(get(row, "op_id"), default=0) or 0,
            machine_id=_text_or_none(get(row, "machine_id")),
            operator_id=_text_or_none(get(row, "operator_id")),
            start_time=str(get(row, "start_time") or ""),
            end_time=str(get(row, "end_time") or ""),
            lock_status=str(get(row, "lock_status") or LockStatus.UNLOCKED.value),
            created_at=_text_or_none(get(row, "created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)


@dataclass
class ScheduleCandidateSelection:
    id: Optional[int]
    version: int
    role: str
    candidate_id: int
    source_table: str
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleCandidateSelection:
        return cls(
            id=parse_int(get(row, "id"), default=None),
            version=parse_int(get(row, "version"), default=0) or 0,
            role=str(get(row, "role") or ""),
            candidate_id=parse_int(get(row, "candidate_id"), default=0) or 0,
            source_table=str(get(row, "source_table") or ""),
            created_at=_text_or_none(get(row, "created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)
