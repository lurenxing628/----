"""Input derivation and the shared search budget boundary."""

from __future__ import annotations

import math
from dataclasses import is_dataclass, replace
from types import SimpleNamespace
from typing import Any, Optional, cast

from core.errors import ValidationError


def _replace_schedule_input_cfg(schedule_input: Any, *, cfg: Any) -> Any:
    if is_dataclass(schedule_input) and not isinstance(schedule_input, type):
        return replace(cast(Any, schedule_input), cfg=cfg)
    if hasattr(schedule_input, "__dict__"):
        data = dict(vars(schedule_input))
        data["cfg"] = cfg
        return SimpleNamespace(**data)
    raise TypeError("schedule_input 必须是 dataclass 或普通对象，才能构造候选级输入。")


def _resolve_total_budget(run_time_budget_seconds: Optional[float], *, cfg: Any) -> float:
    if run_time_budget_seconds is None:
        return float(cfg.time_budget_seconds)
    if isinstance(run_time_budget_seconds, bool):
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds")
    try:
        budget = float(run_time_budget_seconds)
    except Exception as exc:
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds") from exc
    if math.isnan(budget) or budget <= 0:
        raise ValidationError("这次找更好排法先试多久必须大于 0 秒。", field="run_time_budget_seconds")
    return budget


def _public_budget(total_budget: float) -> Optional[float]:
    if not math.isfinite(total_budget):
        return None
    return float(total_budget)
