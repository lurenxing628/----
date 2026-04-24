from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.common.safe_logging import safe_warning

from ..number_utils import parse_finite_float, parse_finite_int
from .config_field_spec import get_field_spec, list_config_fields
from .config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
from .config_validator import normalize_preset_snapshot as normalize_preset_snapshot_dict


def _preset_result(
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


def builtin_presets(svc: Any) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
    """
    返回内置模板列表：(name, snapshot, description)。
    - 仅在缺失时创建，不覆盖用户自定义模板
    """
    base = svc._default_snapshot()
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
        (svc.BUILTIN_PRESET_DEFAULT, base, "默认方案：快速、稳定（推荐日常使用）"),
        (svc.BUILTIN_PRESET_DUE_FIRST, due_first, "交期优先：更关注交期（适合赶交付场景）"),
        (svc.BUILTIN_PRESET_MIN_CHANGEOVER, min_changeover, "换型最少：倾向减少换型（可能更慢）"),
        (svc.BUILTIN_PRESET_IMPROVE_SLOW, improve_slow, "改进更优：允许更长搜索时间（更慢）"),
    ]


def snapshot_close(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> bool:
    return not snapshot_diff_fields(a, b)


def _values_close(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


def snapshot_diff_fields(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> List[str]:
    left = a.to_dict()
    right = b.to_dict()
    diff_fields: List[str] = []
    for key, expected in left.items():
        if key not in right or not _values_close(expected, right.get(key)):
            diff_fields.append(str(key))
    for key in right.keys():
        if key not in left:
            diff_fields.append(str(key))
    return list(dict.fromkeys(diff_fields))


def _preset_mismatch_reason(svc: Any, fields: List[str]) -> str:
    sample = "、".join([str(field) for field in (fields or [])[:5]])
    return svc.ACTIVE_PRESET_REASON_PRESET_MISMATCH if not sample else f"{svc.ACTIVE_PRESET_REASON_PRESET_MISMATCH} 涉及字段：{sample}。"


def _preset_adjusted_reason(svc: Any, fields: List[str]) -> str:
    sample = "、".join([str(field) for field in (fields or [])[:5]])
    return svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED if not sample else f"{svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED} 涉及字段：{sample}。"


def _registered_preset_keys() -> Tuple[str, ...]:
    return tuple(spec.key for spec in list_config_fields())


def _missing_required_preset_fields(data: Dict[str, Any]) -> List[str]:
    payload = dict(data or {})
    return [key for key in _registered_preset_keys() if key not in payload]


def _raw_value_matches_canonical(key: str, raw_value: Any, canonical_value: Any) -> bool:
    spec = get_field_spec(key)
    if spec.field_type in ("enum", "yes_no"):
        return isinstance(raw_value, str) and raw_value == str(canonical_value)

    try:
        if spec.field_type == "float":
            return _values_close(parse_finite_float(raw_value, field=key, allow_none=False), canonical_value)
        if spec.field_type == "int":
            return _values_close(parse_finite_int(raw_value, field=key, allow_none=False), canonical_value)
    except Exception:
        return False

    return raw_value == canonical_value


def snapshot_payload_projection_diff_fields(data: Dict[str, Any], snapshot: ScheduleConfigSnapshot) -> List[str]:
    payload = dict(data or {})
    canonical = snapshot.to_dict()
    diff_fields: List[str] = []
    registered_keys = set(_registered_preset_keys())
    for key in _registered_preset_keys():
        if key not in canonical:
            continue
        if key not in payload:
            diff_fields.append(key)
            continue
        if not _raw_value_matches_canonical(key, payload.get(key), canonical[key]):
            diff_fields.append(key)
    for key in payload.keys():
        if key not in registered_keys:
            diff_fields.append(str(key))
    return list(dict.fromkeys(diff_fields))


def get_snapshot_from_repo(svc: Any, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
    return build_schedule_config_snapshot(
        svc.repo,
        strict_mode=bool(strict_mode),
    )


def ensure_builtin_presets(svc: Any, *, existing_keys: Optional[set] = None) -> None:
    """
    确保内置模板与 active_preset 存在（缺失则创建，不覆盖用户配置）。
    """
    keys = existing_keys if existing_keys is not None else {c.config_key for c in svc.repo.list_all()}
    presets_to_create: List[Tuple[str, str, str]] = []
    for name, snap, desc in builtin_presets(svc):
        k = svc._preset_key(name)
        if k in keys:
            continue
        presets_to_create.append(
            (
                k,
                json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),
                f"排产配置模板：{desc}",
            )
        )

    if not presets_to_create:
        return

    with svc.tx_manager.transaction():
        for k, v, d in presets_to_create:
            svc.repo.set(k, v, description=d)


def bootstrap_active_provenance_if_pristine(svc: Any) -> None:
    active_value = None
    active_reason = None
    try:
        if bool((svc.get_preset_display_state(readonly=True) or {}).get("can_preserve_baseline")):
            return

        cur = get_snapshot_from_repo(svc)
        default_snap = svc._default_snapshot()
        if getattr(cur, "degradation_counters", None):
            active_value = svc.ACTIVE_PRESET_CUSTOM
            active_reason = svc.ACTIVE_PRESET_REASON_BASELINE_DEGRADED
        elif snapshot_close(cur, default_snap):
            active_value = svc.BUILTIN_PRESET_DEFAULT
            active_reason = None
        else:
            active_value = svc.ACTIVE_PRESET_CUSTOM
            active_reason = svc.ACTIVE_PRESET_REASON_BASELINE_MISMATCH
    except Exception as exc:
        active_value = svc.ACTIVE_PRESET_CUSTOM
        active_reason = f"{svc.ACTIVE_PRESET_REASON_BASELINE_DEGRADED} 原因：{type(exc).__name__}"
        safe_warning(getattr(svc, "logger", None), f"初始化 active_preset 基线探测失败，已标记为 degraded：{exc}")

    with svc.tx_manager.transaction():
        svc.repo.set_batch(svc._active_preset_updates(active_value, reason=active_reason))


def list_presets(svc: Any) -> List[Dict[str, Any]]:
    state = svc.get_preset_display_state(readonly=True)
    return list(state.get("presets") or [])


def _readonly_active_preset_state(svc: Any) -> Dict[str, Any]:
    state = svc.get_preset_display_state(readonly=True)
    active_preset = str(state.get("active_preset") or "").strip()
    provenance_missing = bool(state.get("provenance_missing"))
    return {
        "effective_active_preset": active_preset if active_preset and not provenance_missing else svc.ACTIVE_PRESET_CUSTOM,
        "reason": state.get("active_preset_reason") if active_preset and not provenance_missing else None,
    }


def _builtin_preset_payload(svc: Any, name: str) -> Optional[Dict[str, Any]]:
    for preset_name, snapshot, _description in builtin_presets(svc):
        if str(preset_name or "").strip() != str(name or "").strip():
            continue
        return dict(snapshot.to_dict())
    return None


def _load_preset_payload(svc: Any, name: str) -> Dict[str, Any]:
    builtin_payload = _builtin_preset_payload(svc, name)
    if builtin_payload is not None:
        return builtin_payload

    raw = svc.repo.get_value(svc._preset_key(name), default=None)
    if raw is None or str(raw).strip() == "":
        raise BusinessError(ErrorCode.NOT_FOUND, f"未找到方案：{name}")

    try:
        data = json.loads(str(raw))
        if not isinstance(data, dict):
            raise ValueError("preset json is not dict")
        return dict(data)
    except Exception as exc:
        raise ValidationError("方案数据已损坏，暂时无法读取。", field="方案数据") from exc


def try_load_preset_snapshot_for_baseline(svc: Any, name: str) -> Tuple[Optional[ScheduleConfigSnapshot], bool]:
    preset_name = str(name or "").strip()
    if not preset_name or preset_name.lower() == str(svc.ACTIVE_PRESET_CUSTOM).strip().lower():
        return None, False
    try:
        # baseline probe must use the same canonical preset source as apply_preset:
        # builtin presets prefer code-bundled payloads, named presets prefer repo rows.
        data = _load_preset_payload(svc, preset_name)
    except (BusinessError, ValidationError, TypeError, ValueError, json.JSONDecodeError):
        return None, True
    if _missing_required_preset_fields(data):
        return None, True
    try:
        return normalize_preset_snapshot(svc, data), False
    except ValidationError:
        return None, True


def save_preset(svc: Any, name: Any) -> Dict[str, Any]:
    n = svc._normalize_text(name)
    if not n:
        raise ValidationError("方案名称不能为空", field="方案名称")
    if len(n) > 50:
        raise ValidationError("方案名称过长，建议不要超过 50 个字。", field="方案名称")
    if svc._is_builtin_preset(n):
        raise ValidationError("系统自带方案不能覆盖，请换个名字另存。", field="方案名称")

    try:
        snap = svc.get_snapshot(strict_mode=True)
    except ValidationError as exc:
        readonly_state = _readonly_active_preset_state(svc)
        return _preset_result(
            requested_preset=n,
            effective_active_preset=str(readonly_state["effective_active_preset"]),
            status="rejected",
            adjusted_fields=[],
            reason=readonly_state["reason"],
            error_field=str(getattr(exc, "field", "") or ""),
            error_fields=[str(getattr(exc, "field", "") or "").strip()] if str(getattr(exc, "field", "") or "").strip() else [],
            error_message=str(exc.message),
        )
    payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)
    with svc.tx_manager.transaction():
        svc.repo.set(svc._preset_key(n), payload, description="排产配置模板（用户自定义）")
        svc.repo.set_batch(svc._active_preset_updates(n))
    return _preset_result(
        requested_preset=n,
        effective_active_preset=n,
        status="saved",
        adjusted_fields=[],
        reason=None,
    )


def delete_preset(svc: Any, name: Any) -> None:
    n = svc._normalize_text(name)
    if not n:
        raise ValidationError("方案名称不能为空", field="方案名称")
    if svc._is_builtin_preset(n):
        raise ValidationError("系统自带方案不能删除。", field="方案名称")

    active = svc.get_active_preset()
    with svc.tx_manager.transaction():
        svc.repo.delete(svc._preset_key(n))
        if active == n:
            svc.repo.set_batch(svc._active_preset_updates(svc.ACTIVE_PRESET_CUSTOM, reason=svc.ACTIVE_PRESET_REASON_PRESET_DELETED))


def normalize_preset_snapshot(svc: Any, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
    """
    将 JSON 里的 snapshot dict 归一化为合法 ScheduleConfigSnapshot。
    apply 路径要求数据本身合法；仅允许缺字段按 base 回退。
    """
    base = svc._default_snapshot()
    return normalize_preset_snapshot_dict(
        data,
        base=base,
        strict_mode=True,
    )


def apply_preset(svc: Any, name: Any) -> Dict[str, Any]:
    n = svc._normalize_text(name)
    if not n:
        raise ValidationError("方案名称不能为空", field="方案名称")

    data = _load_preset_payload(svc, n)

    missing_fields = _missing_required_preset_fields(data)
    if missing_fields:
        readonly_state = _readonly_active_preset_state(svc)
        sample = "、".join(str(field) for field in missing_fields)
        return _preset_result(
            requested_preset=n,
            effective_active_preset=str(readonly_state["effective_active_preset"]),
            status="rejected",
            adjusted_fields=[],
            reason=readonly_state["reason"],
            error_field=str(missing_fields[0]),
            error_fields=list(missing_fields),
            error_message=f"方案缺少必填字段：{sample}。",
        )

    snap = normalize_preset_snapshot(svc, data)
    payload_diff_fields = snapshot_payload_projection_diff_fields(data, snap)
    config_updates = [(key, str(value), None) for key, value in snap.to_dict().items()]

    with svc.tx_manager.transaction():
        svc.repo.set_batch(config_updates)
        final_snap = get_snapshot_from_repo(svc, strict_mode=True)
        diff_fields = snapshot_diff_fields(snap, final_snap)
        if diff_fields:
            combined_fields = list(dict.fromkeys(list(payload_diff_fields) + list(diff_fields)))
            reason = _preset_mismatch_reason(svc, combined_fields)
            svc.repo.set_batch(
                svc._active_preset_updates(
                    n,
                    reason=reason,
                )
            )
            effective_active_preset = n
            adjusted_fields = combined_fields
            status = "adjusted"
        elif payload_diff_fields:
            reason = _preset_adjusted_reason(svc, payload_diff_fields)
            svc.repo.set_batch(
                svc._active_preset_updates(
                    n,
                    reason=reason,
                )
            )
            effective_active_preset = n
            adjusted_fields = list(payload_diff_fields)
            status = "adjusted"
        else:
            svc.repo.set_batch(svc._active_preset_updates(n))
            reason = None
            effective_active_preset = n
            adjusted_fields = []
            status = "applied"

    return _preset_result(
        requested_preset=n,
        effective_active_preset=effective_active_preset,
        status=status,
        adjusted_fields=adjusted_fields,
        reason=reason,
    )
