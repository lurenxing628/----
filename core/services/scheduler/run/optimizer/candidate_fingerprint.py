from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics
from core.models.objective import objective_metric_keys


@dataclass(frozen=True)
class CandidateFingerprint:
    output_key: Tuple[Any, ...] = field(repr=False)
    same_as_parent: bool
    same_as_seen: bool
    fingerprint_changed: bool

    def with_context(self, *, parent_fingerprint: Optional[CandidateFingerprint],
                     seen_output_fingerprints: Iterable[Tuple[Any, ...]]) -> CandidateFingerprint:
        same_as_parent = bool(parent_fingerprint is not None and self.output_key == parent_fingerprint.output_key)
        return replace(self, same_as_parent=same_as_parent,
                       same_as_seen=self.output_key in seen_output_fingerprints,
                       fingerprint_changed=not same_as_parent)


def schedule_content_key(results: Iterable[ScheduleResult]) -> Tuple[Tuple[Any, ...], ...]:
    """Identify the actual arrangement independently of its evaluation."""
    return tuple(
        (
            result.op_id,
            result.batch_id,
            result.seq,
            result.machine_id,
            result.operator_id,
            result.start_time,
            result.end_time,
            result.source,
            result.seed_source,
            result.state_revision,
            result.op_type_id,
        )
        for result in sorted(results, key=lambda row: row.op_id)
    )


def build_candidate_fingerprint(
    candidate: Dict[str, Any],
    *,
    objective_name: str,
    parent_fingerprint: Optional[CandidateFingerprint],
    seen_output_fingerprints: Iterable[Tuple[Any, ...]],
    identity: Optional[CandidateFingerprint] = None,
) -> CandidateFingerprint:
    if identity is not None:
        return identity.with_context(parent_fingerprint=parent_fingerprint,
                                     seen_output_fingerprints=seen_output_fingerprints)
    output_key = _evaluation_key(candidate, objective_name=objective_name)
    same_as_parent = bool(parent_fingerprint is not None and output_key == parent_fingerprint.output_key)
    return CandidateFingerprint(
        output_key=output_key,
        same_as_parent=same_as_parent,
        same_as_seen=output_key in seen_output_fingerprints,
        fingerprint_changed=not same_as_parent,
    )


def score_strictly_better(candidate_score: Any, parent_score: Any) -> bool:
    candidate = _score_tuple(candidate_score)
    parent = _score_tuple(parent_score)
    if not candidate or not parent:
        return False
    return candidate < parent


def _evaluation_key(candidate: Dict[str, Any], *, objective_name: str) -> Tuple[Any, ...]:
    metrics: ScheduleMetrics = candidate["metrics"]
    metric_signature = tuple(
        (key, round(float(getattr(metrics, key)), 6)) for key in objective_metric_keys(objective_name)
    )
    summary: ScheduleSummary = candidate["summary"]
    completion = metrics.completion
    completion_summary = (
        completion.expected_operation_count, completion.missing_operation_count,
        completion.unexpected_result_count, completion.complete_batch_count,
        completion.objective_scope, completion.components_known,
    )
    return (candidate["archive_ref"].entry_id, objective_name,
            (summary.success, summary.total_ops, summary.scheduled_ops, summary.failed_ops),
            completion_summary, metric_signature, _score_tuple(candidate.get("score")))


def _score_tuple(score: Any) -> Tuple[float, ...]:
    if not isinstance(score, (list, tuple)) or not score:
        return ()
    return tuple(round(float(item), 6) for item in score)


__all__ = [
    "CandidateFingerprint",
    "build_candidate_fingerprint",
    "schedule_content_key",
    "score_strictly_better",
]
