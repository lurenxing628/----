from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

_BUCKETS = ("fallback_counts", "param_fallbacks")


def ensure_algo_stats(target: Any) -> Dict[str, Any]:
    if isinstance(target, dict):
        stats = target
    else:
        stats = getattr(target, "_last_algo_stats", None)
        if not isinstance(stats, dict):
            stats = {}
            try:
                target._last_algo_stats = stats
            except Exception:
                return {"fallback_counts": {}, "param_fallbacks": {}}

    for bucket in _BUCKETS:
        current = stats.get(bucket)
        if not isinstance(current, dict):
            stats[bucket] = {}
    return stats


def snapshot_algo_stats(target: Any) -> Dict[str, Any]:
    stats = ensure_algo_stats(target)
    try:
        return deepcopy(stats)
    except Exception:
        copied: Dict[str, Any] = {}
        for bucket in _BUCKETS:
            part = stats.get(bucket)
            copied[bucket] = dict(part) if isinstance(part, dict) else {}
        return copied


def increment_counter(target: Any, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
    if not key:
        return
    stats = ensure_algo_stats(target)
    current_bucket = stats.get(bucket)
    if not isinstance(current_bucket, dict):
        current_bucket = {}
        stats[bucket] = current_bucket
    try:
        delta = int(amount)
    except Exception:
        delta = 0
    if delta == 0:
        return
    try:
        current_bucket[key] = int(current_bucket.get(key, 0) or 0) + delta
    except Exception:
        current_bucket[key] = delta


def merge_algo_stats(*sources: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {"fallback_counts": {}, "param_fallbacks": {}}
    for src in sources:
        if not isinstance(src, Mapping):
            continue
        for bucket in _BUCKETS:
            part = src.get(bucket)
            if not isinstance(part, Mapping):
                continue
            bucket_out = merged.get(bucket)
            if not isinstance(bucket_out, dict):
                bucket_out = {}
                merged[bucket] = bucket_out
            for key, value in part.items():
                try:
                    delta = int(value)
                except Exception:
                    continue
                if delta == 0:
                    continue
                bucket_out[key] = int(bucket_out.get(key, 0) or 0) + delta
    return merged
