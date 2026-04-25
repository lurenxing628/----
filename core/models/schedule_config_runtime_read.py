from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.degradation import DegradationCollector, DegradationEvent


def read_runtime_cfg_raw_value(cfg: Any, key: str) -> Tuple[bool, Any]:
    if cfg is None:
        return True, None
    if isinstance(cfg, dict):
        if key in cfg:
            return False, cfg.get(key)
        return True, None

    raw_missing = object()
    try:
        value = getattr(cfg, key, raw_missing)
    except ValidationError:
        raise
    except Exception as exc:
        raise runtime_cfg_read_error(key, exc) from exc
    if value is raw_missing:
        missing, value = _read_runtime_cfg_mapping_like_value(cfg, key, raw_missing)
        if not missing:
            return False, value
        return True, None
    return False, value


def runtime_cfg_read_error(key: str, exc: Exception) -> ValidationError:
    return ValidationError(f"读取运行期配置字段“{key}”失败：{exc}", field=key)


def _read_runtime_cfg_mapping_like_value(cfg: Any, key: str, raw_missing: object) -> Tuple[bool, Any]:
    getter = getattr(cfg, "get", None)
    if not callable(getter):
        return True, None
    try:
        value = getter(key, raw_missing)
    except TypeError:
        value = _read_runtime_cfg_mapping_like_value_without_default(getter, key, raw_missing)
    except KeyError:
        value = raw_missing
    except ValidationError:
        raise
    except Exception as exc:
        raise runtime_cfg_read_error(key, exc) from exc
    if value is raw_missing:
        return True, None
    return False, value


def _read_runtime_cfg_mapping_like_value_without_default(getter: Any, key: str, raw_missing: object) -> Any:
    try:
        return getter(key)
    except KeyError:
        return raw_missing
    except ValidationError:
        raise
    except Exception as exc:
        raise runtime_cfg_read_error(key, exc) from exc


def _coerce_degradation_event(raw: Any) -> Optional[DegradationEvent]:
    if isinstance(raw, DegradationEvent):
        return raw
    if not isinstance(raw, dict):
        return None

    code = str(raw.get("code") or "").strip()
    scope = str(raw.get("scope") or "").strip()
    message = str(raw.get("message") or "").strip()
    if not code or not scope or not message:
        return None

    field_value = raw.get("field")
    field_text = str(field_value).strip() if field_value is not None else ""
    sample_value = raw.get("sample")
    try:
        count = max(1, int(raw.get("count") or 1))
    except Exception:
        count = 1
    return DegradationEvent(
        code=code,
        scope=scope,
        field=field_text or None,
        message=message,
        count=count,
        sample=None if sample_value is None else str(sample_value),
    )


def seed_snapshot_degradation_collector(cfg: Any) -> DegradationCollector:
    collector = DegradationCollector()
    for raw in getattr(cfg, "degradation_events", ()) or ():
        event = _coerce_degradation_event(raw)
        if event is not None:
            collector.add(event)
    return collector


def merge_degradation_counters(*counter_maps: Any) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for counter_map in counter_maps:
        if not isinstance(counter_map, dict):
            continue
        for key, raw_value in counter_map.items():
            text = str(key or "").strip()
            if not text:
                continue
            try:
                count = int(raw_value)
            except Exception:
                continue
            if count <= 0:
                continue
            merged[text] = max(int(merged.get(text) or 0), count)
    return merged


__all__ = [
    "merge_degradation_counters",
    "read_runtime_cfg_raw_value",
    "seed_snapshot_degradation_collector",
]
