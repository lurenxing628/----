from __future__ import annotations

from typing import Any, Dict, Tuple

from core.infrastructure.errors import ValidationError

from .config_snapshot import ScheduleConfigSnapshot
from .number_utils import parse_finite_float, parse_finite_int, to_yes_no


def normalize_preset_snapshot(
    data: Dict[str, Any],
    *,
    base: ScheduleConfigSnapshot,
    valid_strategies: Tuple[str, ...],
    valid_dispatch_modes: Tuple[str, ...],
    valid_dispatch_rules: Tuple[str, ...],
    valid_algo_modes: Tuple[str, ...],
    valid_objectives: Tuple[str, ...],
) -> ScheduleConfigSnapshot:
    def _valid_norm(values: Tuple[str, ...]) -> Tuple[str, ...]:
        out = []
        seen = set()
        for item in values or ():
            text = str(item).strip().lower()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return tuple(out)

    valid_strategies_norm = _valid_norm(valid_strategies)
    valid_dispatch_modes_norm = _valid_norm(valid_dispatch_modes)
    valid_dispatch_rules_norm = _valid_norm(valid_dispatch_rules)
    valid_algo_modes_norm = _valid_norm(valid_algo_modes)
    valid_objectives_norm = _valid_norm(valid_objectives)

    st = str(data.get("sort_strategy") or base.sort_strategy).strip().lower()
    base_strategy = str(base.sort_strategy).strip().lower()
    if st not in valid_strategies_norm:
        st = base_strategy

    def _get_float(key: str, default: float, field: str) -> float:
        raw = data.get(key)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            return float(default)
        v = parse_finite_float(raw, field=field, allow_none=False)
        return float(v if v is not None else default)

    pw = _get_float("priority_weight", float(base.priority_weight), field="优先级权重")
    dw = _get_float("due_weight", float(base.due_weight), field="交期权重")
    if pw < 0 or dw < 0:
        raise ValidationError("权重不能为负数", field="权重")
    percent_mode = (pw > 1.0) or (dw > 1.0)
    if percent_mode:
        if (0 < pw < 1) or (0 < dw < 1):
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if pw > 100.0 or dw > 100.0:
            raise ValidationError("权重范围不合理（期望 0~1 或 0~100%）", field="权重")
        pw = pw / 100.0
        dw = dw / 100.0
    if pw > 1.0 or dw > 1.0:
        raise ValidationError("权重范围不合理（期望 0~1 或 0~100%）", field="权重")
    rw = 1.0 - float(pw) - float(dw)
    if rw < -1e-9:
        raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
    rw = max(0.0, float(rw))

    hde = _get_float("holiday_default_efficiency", float(base.holiday_default_efficiency), field="假期工作效率")
    if hde <= 0:
        hde = float(base.holiday_default_efficiency)

    def _yesno(v: Any, default: str = "no") -> str:
        return to_yes_no(v, default=default)

    enforce_ready_default = _yesno(data.get("enforce_ready_default"), default=str(base.enforce_ready_default))
    prefer_primary_skill = _yesno(data.get("prefer_primary_skill"), default=str(base.prefer_primary_skill))
    auto_assign_enabled = _yesno(data.get("auto_assign_enabled"), default=str(base.auto_assign_enabled))
    ortools_enabled = _yesno(data.get("ortools_enabled"), default=str(base.ortools_enabled))
    freeze_window_enabled = _yesno(data.get("freeze_window_enabled"), default=str(base.freeze_window_enabled))

    dm = str(data.get("dispatch_mode") or base.dispatch_mode).strip().lower()
    base_dispatch_mode = str(base.dispatch_mode).strip().lower()
    if dm not in valid_dispatch_modes_norm:
        dm = base_dispatch_mode
    dr = str(data.get("dispatch_rule") or base.dispatch_rule).strip().lower()
    base_dispatch_rule = str(base.dispatch_rule).strip().lower()
    if dr not in valid_dispatch_rules_norm:
        dr = base_dispatch_rule

    algo_mode = str(data.get("algo_mode") or base.algo_mode).strip().lower()
    base_algo_mode = str(base.algo_mode).strip().lower()
    if algo_mode not in valid_algo_modes_norm:
        algo_mode = base_algo_mode
    objective = str(data.get("objective") or base.objective).strip().lower()
    base_objective = str(base.objective).strip().lower()
    if objective not in valid_objectives_norm:
        objective = base_objective

    def _get_int(key: str, default: int, min_v: int, field: str) -> int:
        raw = data.get(key)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            v = int(default)
        else:
            parsed = parse_finite_int(raw, field=field, allow_none=False)
            v = int(parsed if parsed is not None else default)
        return max(int(min_v), int(v))

    ort_limit = _get_int(
        "ortools_time_limit_seconds",
        int(base.ortools_time_limit_seconds),
        1,
        field="自动优化计算时间",
    )
    time_budget = _get_int("time_budget_seconds", int(base.time_budget_seconds), 1, field="计算时间上限")
    fw_days = _get_int("freeze_window_days", int(base.freeze_window_days), 0, field="锁定天数")

    return ScheduleConfigSnapshot(
        sort_strategy=st,
        priority_weight=float(pw),
        due_weight=float(dw),
        ready_weight=float(rw),
        holiday_default_efficiency=float(hde),
        enforce_ready_default=enforce_ready_default,
        prefer_primary_skill=prefer_primary_skill,
        dispatch_mode=dm,
        dispatch_rule=dr,
        auto_assign_enabled=auto_assign_enabled,
        ortools_enabled=ortools_enabled,
        ortools_time_limit_seconds=int(ort_limit),
        algo_mode=algo_mode,
        time_budget_seconds=int(time_budget),
        objective=objective,
        freeze_window_enabled=freeze_window_enabled,
        freeze_window_days=int(fw_days),
    )

