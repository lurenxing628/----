from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError

from .config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
from .config_validator import normalize_preset_snapshot as normalize_preset_snapshot_dict


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
    def _eq_float(x: float, y: float) -> bool:
        try:
            return abs(float(x) - float(y)) <= 1e-9
        except Exception:
            return False

    checks = [
        a.sort_strategy == b.sort_strategy,
        _eq_float(a.priority_weight, b.priority_weight),
        _eq_float(a.due_weight, b.due_weight),
        _eq_float(a.ready_weight, b.ready_weight),
        _eq_float(a.holiday_default_efficiency, b.holiday_default_efficiency),
        a.enforce_ready_default == b.enforce_ready_default,
        a.prefer_primary_skill == b.prefer_primary_skill,
        a.dispatch_mode == b.dispatch_mode,
        a.dispatch_rule == b.dispatch_rule,
        a.auto_assign_enabled == b.auto_assign_enabled,
        a.ortools_enabled == b.ortools_enabled,
        int(a.ortools_time_limit_seconds) == int(b.ortools_time_limit_seconds),
        a.algo_mode == b.algo_mode,
        int(a.time_budget_seconds) == int(b.time_budget_seconds),
        a.objective == b.objective,
        a.freeze_window_enabled == b.freeze_window_enabled,
        int(a.freeze_window_days) == int(b.freeze_window_days),
    ]
    return all(checks)


def get_snapshot_from_repo(svc: Any) -> ScheduleConfigSnapshot:
    """
    从 repo 读取 snapshot（不调用 ensure_defaults；避免递归）。
    - 缺键时使用默认值
    - 适用于 ensure_defaults 内部调用
    """
    defaults = {
        "sort_strategy": svc.DEFAULT_SORT_STRATEGY,
        "priority_weight": float(svc.DEFAULT_PRIORITY_WEIGHT),
        "due_weight": float(svc.DEFAULT_DUE_WEIGHT),
        "ready_weight": float(svc.DEFAULT_READY_WEIGHT),
        "holiday_default_efficiency": float(svc.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY),
        "enforce_ready_default": str(svc.DEFAULT_ENFORCE_READY_DEFAULT),
        "dispatch_mode": svc.DEFAULT_DISPATCH_MODE,
        "dispatch_rule": svc.DEFAULT_DISPATCH_RULE,
        "auto_assign_enabled": svc.DEFAULT_AUTO_ASSIGN_ENABLED,
        "ortools_enabled": svc.DEFAULT_ORTOOLS_ENABLED,
        "ortools_time_limit_seconds": int(svc.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS),
        "algo_mode": svc.DEFAULT_ALGO_MODE,
        "time_budget_seconds": int(svc.DEFAULT_TIME_BUDGET_SECONDS),
        "objective": svc.DEFAULT_OBJECTIVE,
        "freeze_window_enabled": svc.DEFAULT_FREEZE_WINDOW_ENABLED,
        "freeze_window_days": int(svc.DEFAULT_FREEZE_WINDOW_DAYS),
    }
    return build_schedule_config_snapshot(
        svc.repo,
        defaults=defaults,
        valid_strategies=svc.VALID_STRATEGIES,
        valid_dispatch_modes=svc.VALID_DISPATCH_MODES,
        valid_dispatch_rules=svc.VALID_DISPATCH_RULES,
        valid_algo_modes=svc.VALID_ALGO_MODES,
        valid_objectives=svc.VALID_OBJECTIVES,
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

    # active_preset：老库升级时可能缺失；尽量不误导
    need_active = svc.ACTIVE_PRESET_KEY not in keys
    active_value = None
    if need_active:
        try:
            cur = get_snapshot_from_repo(svc)
            default_snap = svc._default_snapshot()
            active_value = svc.BUILTIN_PRESET_DEFAULT if snapshot_close(cur, default_snap) else svc.ACTIVE_PRESET_CUSTOM
        except Exception:
            active_value = svc.ACTIVE_PRESET_CUSTOM

    if not presets_to_create and not need_active:
        return

    with svc.tx_manager.transaction():
        for k, v, d in presets_to_create:
            svc.repo.set(k, v, description=d)
        if need_active:
            ak, av, ad = svc._active_preset_update(active_value)
            svc.repo.set(ak, av, description=ad)


def list_presets(svc: Any) -> List[Dict[str, Any]]:
    svc.ensure_defaults()
    items = svc.repo.list_all()
    out: List[Dict[str, Any]] = []
    for c in items:
        if not (c.config_key or "").startswith(svc.PRESET_PREFIX):
            continue
        name = str(c.config_key)[len(svc.PRESET_PREFIX) :]
        if not name:
            continue
        out.append({"name": name, "updated_at": c.updated_at, "config_key": c.config_key, "description": c.description})
    out.sort(key=lambda x: x.get("name") or "")
    return out


def save_preset(svc: Any, name: Any) -> str:
    n = svc._normalize_text(name)
    if not n:
        raise ValidationError("方案名称不能为空", field="方案名称")
    if len(n) > 50:
        raise ValidationError("方案名称过长，建议不要超过 50 个字。", field="方案名称")
    if svc._is_builtin_preset(n):
        raise ValidationError("系统自带方案不能覆盖，请换个名字另存。", field="方案名称")

    snap = svc.get_snapshot()
    payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)
    with svc.tx_manager.transaction():
        svc.repo.set(svc._preset_key(n), payload, description="排产配置模板（用户自定义）")
        ak, av, ad = svc._active_preset_update(n)
        svc.repo.set(ak, av, description=ad)
    return n


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
            ak, av, ad = svc._active_preset_update(svc.ACTIVE_PRESET_CUSTOM)
            svc.repo.set(ak, av, description=ad)


def normalize_preset_snapshot(svc: Any, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
    """
    将 JSON 里的 snapshot dict 归一化为合法 ScheduleConfigSnapshot。
    说明：这里做“容错+兜底”，避免模板数据坏了导致整个系统不可用。
    """
    base = svc._default_snapshot()
    return normalize_preset_snapshot_dict(
        data,
        base=base,
        valid_strategies=svc.VALID_STRATEGIES,
        valid_dispatch_modes=svc.VALID_DISPATCH_MODES,
        valid_dispatch_rules=svc.VALID_DISPATCH_RULES,
        valid_algo_modes=svc.VALID_ALGO_MODES,
        valid_objectives=svc.VALID_OBJECTIVES,
    )


def apply_preset(svc: Any, name: Any) -> str:
    n = svc._normalize_text(name)
    if not n:
        raise ValidationError("方案名称不能为空", field="方案名称")

    svc.ensure_defaults()
    raw = svc.repo.get_value(svc._preset_key(n), default=None)
    if raw is None or str(raw).strip() == "":
        raise BusinessError(ErrorCode.NOT_FOUND, f"未找到方案：{n}")

    try:
        data = json.loads(str(raw))
        if not isinstance(data, dict):
            raise ValueError("preset json is not dict")
    except Exception as e:
        raise ValidationError("方案数据已损坏，暂时无法读取。", field="方案数据") from e

    snap = normalize_preset_snapshot(svc, data)

    # 原子写入：一次性更新所有配置键 + active_preset
    updates = [
        ("sort_strategy", snap.sort_strategy, None),
        ("priority_weight", str(float(snap.priority_weight)), None),
        ("due_weight", str(float(snap.due_weight)), None),
        ("ready_weight", str(float(snap.ready_weight)), None),
        ("holiday_default_efficiency", str(float(snap.holiday_default_efficiency)), None),
        ("enforce_ready_default", str(snap.enforce_ready_default), None),
        ("prefer_primary_skill", str(snap.prefer_primary_skill), None),
        ("dispatch_mode", str(snap.dispatch_mode), None),
        ("dispatch_rule", str(snap.dispatch_rule), None),
        ("auto_assign_enabled", str(snap.auto_assign_enabled), None),
        ("ortools_enabled", str(snap.ortools_enabled), None),
        ("ortools_time_limit_seconds", str(int(snap.ortools_time_limit_seconds)), None),
        ("algo_mode", str(snap.algo_mode), None),
        ("time_budget_seconds", str(int(snap.time_budget_seconds)), None),
        ("objective", str(snap.objective), None),
        ("freeze_window_enabled", str(snap.freeze_window_enabled), None),
        ("freeze_window_days", str(int(snap.freeze_window_days)), None),
        svc._active_preset_update(n),
    ]
    with svc.tx_manager.transaction():
        svc.repo.set_batch(updates)

    return n

