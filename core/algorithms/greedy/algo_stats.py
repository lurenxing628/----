from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

from core.algorithm_runtime.algo_stats import (
    _BUCKETS,
    _COUNTER_BUCKETS,
    _SAMPLE_BUCKETS,
    _empty_stats,
    _strict_int,
    ensure_algo_stats,
    increment_counter,
    make_algo_stats,
)


def snapshot_algo_stats(target: Any) -> Dict[str, Any]:
    stats = ensure_algo_stats(target)
    try:
        return deepcopy(stats)
    except Exception:
        copied = _empty_stats()
        for bucket in _COUNTER_BUCKETS:
            part = stats.get(bucket)
            copied[bucket] = dict(part) if isinstance(part, dict) else {}
        for bucket in _SAMPLE_BUCKETS:
            part = stats.get(bucket)
            bucket_copy: Dict[str, Any] = {}
            if isinstance(part, dict):
                for key, value in part.items():
                    bucket_copy[str(key)] = deepcopy(value) if isinstance(value, list) else []
            copied[bucket] = bucket_copy
        return copied


def merge_algo_stats(*sources: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = _empty_stats()
    for src in sources:
        if not isinstance(src, Mapping):
            continue
        _merge_counter_buckets(merged, src)
        _merge_sample_buckets(merged, src)
    return merged


def _merge_counter_buckets(merged: Dict[str, Any], src: Mapping[str, Any]) -> None:
    for bucket in _COUNTER_BUCKETS:
        part = src.get(bucket)
        if not isinstance(part, Mapping):
            continue
        bucket_out = merged.get(bucket)
        if not isinstance(bucket_out, dict):
            bucket_out = {}
            merged[bucket] = bucket_out
        for key, value in part.items():
            delta = _strict_int(value, label=f"算法统计合并计数 {bucket}.{key}")
            if delta == 0:
                continue
            bucket_out[key] = int(bucket_out.get(key, 0) or 0) + delta


def _merge_sample_buckets(merged: Dict[str, Any], src: Mapping[str, Any]) -> None:
    for bucket in _SAMPLE_BUCKETS:
        part = src.get(bucket)
        if not isinstance(part, Mapping):
            continue
        bucket_out = merged.get(bucket)
        if not isinstance(bucket_out, dict):
            bucket_out = {}
            merged[bucket] = bucket_out
        for key, value in part.items():
            if not isinstance(value, list) or not value:
                continue
            existing = bucket_out.get(key)
            existing_list = deepcopy(existing) if isinstance(existing, list) else []
            existing_list.extend(deepcopy(value))
            bucket_out[str(key)] = existing_list
