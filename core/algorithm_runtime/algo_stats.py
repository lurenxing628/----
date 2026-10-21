from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

_COUNTER_BUCKETS = ("fallback_counts", "param_fallbacks")
_SAMPLE_BUCKETS = ("fallback_samples",)
_BUCKETS = _COUNTER_BUCKETS + _SAMPLE_BUCKETS


def make_algo_stats() -> Dict[str, Any]:
    return {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}


def _strict_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label}必须是整数：{value!r}")
    try:
        converted = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label}必须是整数：{value!r}") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label}必须是整数：{value!r}")
    if not isinstance(value, str):
        try:
            if value != converted:
                raise ValueError(f"{label}必须是整数：{value!r}")
        except TypeError as exc:
            raise ValueError(f"{label}必须是整数：{value!r}") from exc
    if isinstance(value, str):
        text = value.strip()
        if text and text not in {str(converted), f"+{converted}"}:
            raise ValueError(f"{label}必须是整数：{value!r}")
    return converted


def ensure_algo_stats(target: Any) -> Dict[str, Any]:
    if target is None:
        return make_algo_stats()
    if isinstance(target, dict):
        stats = target
    else:
        stats = getattr(target, "_last_algo_stats", None)
        if not isinstance(stats, dict):
            stats = {}
            try:
                target._last_algo_stats = stats
            except (AttributeError, TypeError) as exc:
                raise RuntimeError("算法降级统计无法挂到当前排产对象，不能静默丢弃。") from exc

    for bucket in _BUCKETS:
        current = stats.get(bucket)
        if not isinstance(current, dict):
            stats[bucket] = {}
    return stats


def increment_counter(target: Any, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
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
    delta = _strict_int(amount, label="算法统计增量")
    if delta == 0:
        return
    current_bucket[key] = _strict_int(current_bucket.get(key, 0) or 0, label=f"算法统计已有计数 {key}") + delta


def merge_algo_stats(*sources: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = make_algo_stats()
    for src in sources:
        if not isinstance(src, Mapping):
            continue
        _merge_counter_buckets(merged, src)
        _merge_sample_buckets(merged, src)
    return merged


def capture_algo_stats(target: Any, *sources: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Produce independent merged statistics directly from the decoder's current facts."""
    return merge_algo_stats(*sources, ensure_algo_stats(target))


def _merge_counter_buckets(merged: Dict[str, Any], src: Mapping[str, Any]) -> None:
    for bucket in _COUNTER_BUCKETS:
        part = src.get(bucket)
        if not isinstance(part, Mapping):
            continue
        bucket_out = merged[bucket]
        for key, value in part.items():
            delta = _strict_int(value, label=f"算法统计合并计数 {bucket}.{key}")
            if delta == 0:
                continue
            bucket_out[key] = bucket_out.get(key, 0) + delta


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
            existing_list.extend(deepcopy(value))
            bucket_out[str(key)] = existing_list
