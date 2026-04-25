from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError

from ..number_utils import parse_finite_float, parse_finite_int
from .config_constants import (
    BUILTIN_PRESET_DEFAULT,
    BUILTIN_PRESET_DUE_FIRST,
    BUILTIN_PRESET_IMPROVE_SLOW,
    BUILTIN_PRESET_MIN_CHANGEOVER,
    PRESET_PREFIX,
)
from .config_field_spec import get_field_spec, list_config_fields
from .config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
from .config_validator import normalize_preset_snapshot as normalize_preset_snapshot_dict


def preset_key(name: str) -> str:
    return f"{PRESET_PREFIX}{str(name or '').strip()}"


def preset_result(
    *,
    requested_preset: str,
    effective_active_preset: str,
    status: str,
    adjusted_fields: Optional[List[str]] = None,
    reason: Optional[str] = None,
    error_field: Optional[str] = None,
    error_fields: Optional[List[str]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "requested_preset": str(requested_preset or "").strip(),
        "effective_active_preset": str(effective_active_preset or "").strip(),
        "status": str(status or "").strip(),
        "adjusted_fields": list(adjusted_fields or []),
        "reason": reason,
        "error_field": error_field,
        "error_fields": list(error_fields or []),
        "error_message": error_message,
    }


def builtin_presets(default_snapshot: ScheduleConfigSnapshot) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
    base = default_snapshot
    due_first = ScheduleConfigSnapshot(
        **{
            **base.to_dict(),
            "sort_strategy": "due_date_first",
            "priority_weight": 0.2,
            "due_weight": 0.7,
            "ready_weight": 0.1,
        }
    )
    min_changeover = ScheduleConfigSnapshot(
        **{
            **base.to_dict(),
            "algo_mode": "improve",
            "time_budget_seconds": 30,
            "objective": "min_changeover",
        }
    )
    improve_slow = ScheduleConfigSnapshot(
        **{
            **base.to_dict(),
            "algo_mode": "improve",
            "time_budget_seconds": 120,
            "objective": "min_tardiness",
        }
    )
    return [
        (BUILTIN_PRESET_DEFAULT, base, "默认方案：快速、稳定（推荐日常使用）"),
        (BUILTIN_PRESET_DUE_FIRST, due_first, "交期优先：更关注交期（适合赶交付场景）"),
        (BUILTIN_PRESET_MIN_CHANGEOVER, min_changeover, "换型最少：倾向减少换型（可能更慢）"),
        (BUILTIN_PRESET_IMPROVE_SLOW, improve_slow, "改进更优：允许更长搜索时间（更慢）"),
    ]


def snapshot_close(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> bool:
    return not snapshot_diff_fields(a, b)


def values_close(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


def snapshot_diff_fields(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> List[str]:
    left = a.to_dict()
    right = b.to_dict()
    diff_fields: List[str] = []
    for key, expected in left.items():
        if key not in right or not values_close(expected, right.get(key)):
            diff_fields.append(str(key))
    for key in right.keys():
        if key not in left:
            diff_fields.append(str(key))
    return list(dict.fromkeys(diff_fields))


def registered_preset_keys() -> Tuple[str, ...]:
    return tuple(spec.key for spec in list_config_fields())


def missing_required_preset_fields(data: Dict[str, Any]) -> List[str]:
    payload = dict(data or {})
    return [key for key in registered_preset_keys() if key not in payload]


def raw_value_matches_canonical(key: str, raw_value: Any, canonical_value: Any) -> bool:
    spec = get_field_spec(key)
    if spec.field_type in ("enum", "yes_no"):
        return isinstance(raw_value, str) and raw_value == str(canonical_value)

    try:
        if spec.field_type == "float":
            return values_close(parse_finite_float(raw_value, field=key, allow_none=False), canonical_value)
        if spec.field_type == "int":
            return values_close(parse_finite_int(raw_value, field=key, allow_none=False), canonical_value)
    except Exception:
        return False

    return raw_value == canonical_value


def snapshot_payload_projection_diff_fields(data: Dict[str, Any], snapshot: ScheduleConfigSnapshot) -> List[str]:
    payload = dict(data or {})
    canonical = snapshot.to_dict()
    diff_fields: List[str] = []
    registered_keys = set(registered_preset_keys())
    for key in registered_preset_keys():
        if key not in canonical:
            continue
        if key not in payload:
            diff_fields.append(key)
            continue
        if not raw_value_matches_canonical(key, payload.get(key), canonical[key]):
            diff_fields.append(key)
    for key in payload.keys():
        if key not in registered_keys:
            diff_fields.append(str(key))
    return list(dict.fromkeys(diff_fields))


def get_snapshot_from_repo(repo: Any, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
    return build_schedule_config_snapshot(
        repo,
        strict_mode=bool(strict_mode),
    )


def dump_snapshot_payload(snapshot: ScheduleConfigSnapshot) -> str:
    return json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True)


def load_preset_payload(raw: Any, *, name: str) -> Dict[str, Any]:
    if raw is None or str(raw).strip() == "":
        raise BusinessError(ErrorCode.NOT_FOUND, f"未找到方案：{name}")
    try:
        data = json.loads(str(raw))
        if not isinstance(data, dict):
            raise ValueError("preset json is not dict")
        return dict(data)
    except Exception as exc:
        raise ValidationError("方案数据已损坏，暂时无法读取。", field="方案数据") from exc


def normalize_preset_snapshot(data: Dict[str, Any], *, base: ScheduleConfigSnapshot) -> ScheduleConfigSnapshot:
    return normalize_preset_snapshot_dict(
        data,
        base=base,
        strict_mode=True,
    )


__all__ = [
    "builtin_presets",
    "dump_snapshot_payload",
    "get_snapshot_from_repo",
    "load_preset_payload",
    "missing_required_preset_fields",
    "normalize_preset_snapshot",
    "preset_key",
    "preset_result",
    "registered_preset_keys",
    "snapshot_close",
    "snapshot_diff_fields",
    "snapshot_payload_projection_diff_fields",
    "values_close",
]
