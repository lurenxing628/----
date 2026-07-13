from __future__ import annotations

from typing import Any, Dict

_COUNTER_BUCKETS = ("fallback_counts", "param_fallbacks")
_SAMPLE_BUCKETS = ("fallback_samples",)
_BUCKETS = _COUNTER_BUCKETS + _SAMPLE_BUCKETS


def _empty_stats() -> Dict[str, Any]:
    return {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}


def make_algo_stats() -> Dict[str, Any]:
    return _empty_stats()


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
        return _empty_stats()
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
    current_bucket = stats.get(bucket)
    if not isinstance(current_bucket, dict):
        current_bucket = {}
        stats[bucket] = current_bucket
    delta = _strict_int(amount, label="算法统计增量")
    if delta == 0:
        return
    current_bucket[key] = _strict_int(current_bucket.get(key, 0) or 0, label=f"算法统计已有计数 {key}") + delta
