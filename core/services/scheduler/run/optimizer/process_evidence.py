"""Elapsed-time sampling for the shared optimizer process writer."""
from __future__ import annotations

from typing import Any, Dict, List

POINT_BUDGET = 200
SAMPLING_POLICY = "elapsed_equal_width_bucket_end_best_v1"
_MANDATORY = ("first_valid", "first_expected_complete", "final")
_MANDATORY_SET = frozenset(_MANDATORY)


def sample_elapsed_points(points: List[Dict[str, Any]], *, elapsed_ms: int):
    """Keep milestones and the last incumbent event in each equal elapsed-time bucket (POINT_BUDGET points)."""
    mandatory = {index for index, row in enumerate(points) if not _MANDATORY_SET.isdisjoint(row.get("flags", ()))}
    slots = max(POINT_BUDGET - len(mandatory), 0)
    buckets: Dict[int, int] = {}
    if slots:
        for index, row in enumerate(points):
            bucket = min(int(row["elapsed_ms"] * slots / elapsed_ms), slots - 1) if elapsed_ms else 0
            buckets[bucket] = index
    selected = sorted(mandatory | set(buckets.values()))
    return [points[index] for index in selected], {
        "policy": SAMPLING_POLICY, "point_budget": POINT_BUDGET, "event_total_count": len(points),
        "retained_point_count": len(selected), "bucket_count": slots,
        "bucket_width_ms": elapsed_ms / slots if slots else None, "mandatory": list(_MANDATORY),
    }


__all__ = ["POINT_BUDGET", "SAMPLING_POLICY", "sample_elapsed_points"]
