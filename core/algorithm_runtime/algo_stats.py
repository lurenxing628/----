from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

_COUNTER_BUCKETS = ("fallback_counts", "param_fallbacks")
_SAMPLE_BUCKETS = ("fallback_samples",)
_BUCKETS = _COUNTER_BUCKETS + _SAMPLE_BUCKETS


def make_algo_stats() -> Dict[str, Any]:
    return {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}


def ensure_algo_stats(stats: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """补齐调用方统计字典的固定分桶；``None`` 表示本次不留存，返回一份新字典。"""
    if stats is None:
        return make_algo_stats()
    for bucket in _BUCKETS:
        current = stats.get(bucket)
        if not isinstance(current, dict):
            stats[bucket] = {}
    return stats


def increment_counter(
    target: Optional[Dict[str, Any]], key: str, amount: int = 1, *, bucket: str = "fallback_counts",
) -> None:
    if not key:
        return
    stats = ensure_algo_stats(target)
    if bucket in _BUCKETS:
        current_bucket = stats[bucket]
    else:
        current_bucket = stats.get(bucket)
        if not isinstance(current_bucket, dict):
            current_bucket = {}
            stats[bucket] = current_bucket
    # Counts are the decoder's own integers (len()/counters/event.count); they are summed as given.
    if amount == 0:
        return
    current_bucket[key] = current_bucket.get(key, 0) + amount


def merge_algo_stats(*sources: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = make_algo_stats()
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
        bucket_out = merged[bucket]
        for key, value in part.items():
            if value == 0:
                continue
            bucket_out[key] = bucket_out.get(key, 0) + value


def _merge_sample_buckets(merged: Dict[str, Any], src: Mapping[str, Any]) -> None:
    for bucket in _SAMPLE_BUCKETS:
        part = src.get(bucket)
        if not isinstance(part, Mapping):
            continue
        bucket_out = merged[bucket]
        for key, value in part.items():
            if not isinstance(value, list) or not value:
                continue
            existing = bucket_out.get(key)
            existing_list = existing if isinstance(existing, list) else []
            # 合并结果自带新列表；样本条目只读，下游只会整桶丢弃（summary_size_guard），不改条目本身。
            existing_list.extend(value)
            bucket_out[str(key)] = existing_list
