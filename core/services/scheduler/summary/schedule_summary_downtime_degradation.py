from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import YesNo
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.degradation_messages import (
    DOWNTIME_EXTEND_FAILED_MESSAGE,
    DOWNTIME_LOAD_FAILED_MESSAGE,
)

from .summary_count_parse import _meta_bool_state

_DOWNTIME_META_KEYS = {
    "load_ok": "downtime_load_ok",
    "load_partial_count": "downtime_partial_fail_count",
    "load_partial_sample": "downtime_partial_fail_machines_sample",
    "extend_attempted": "downtime_extend_attempted",
    "extend_ok": "downtime_extend_ok",
    "extend_partial_count": "downtime_extend_partial_fail_count",
    "extend_partial_sample": "downtime_extend_partial_fail_machines_sample",
}


def _meta_int_state(meta: Dict[str, Any], key: str) -> Tuple[int, bool]:
    try:
        return max(0, int(meta.get(key) or 0)), False
    except (TypeError, ValueError, OverflowError):
        return 0, True


def _meta_sample(meta: Dict[str, Any], key: str, *, limit: int = 5) -> List[str]:
    raw = meta.get(key)
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    for item in raw:
        try:
            text = str(item).strip()
        except Exception:
            continue
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _partial_fail_reason(prefix: str, count: int, sample: List[str], suffix: str) -> str:
    sample_text = "、".join(sample)
    message = f"{prefix}（{count} 台"
    if sample_text:
        message += f"，如：{sample_text}"
    return message + f"），{suffix}"


def _downtime_reason(
    *,
    auto_assign_enabled: bool,
    downtime_extend_attempted: bool,
    load_failed: bool,
    load_partial_fail_count: int,
    load_partial_fail_machines_sample: List[str],
    extend_failed: bool,
    extend_partial_fail_count: int,
    extend_partial_fail_machines_sample: List[str],
    meta_parse_failed: bool,
) -> Optional[str]:
    if load_partial_fail_count > 0:
        return _partial_fail_reason(
            "部分设备停机区间加载失败",
            load_partial_fail_count,
            load_partial_fail_machines_sample,
            "这些设备本次先不使用停机约束",
        )
    if meta_parse_failed:
        return "停机资料状态读取异常，本次按停机资料不完整处理；请联系维护人员检查停机资料。"
    if load_failed:
        return DOWNTIME_LOAD_FAILED_MESSAGE
    if auto_assign_enabled and downtime_extend_attempted and extend_partial_fail_count > 0:
        return _partial_fail_reason(
            "部分自动安排设备停机区间扩展加载失败",
            extend_partial_fail_count,
            extend_partial_fail_machines_sample,
            "这些设备可能未覆盖停机约束",
        )
    if extend_failed:
        return DOWNTIME_EXTEND_FAILED_MESSAGE
    return None


def _downtime_meta_state(meta: Dict[str, Any]) -> Dict[str, Any]:
    downtime_load_ok, downtime_load_ok_parse_failed = _meta_bool_state(meta, _DOWNTIME_META_KEYS["load_ok"], default=True)
    load_partial_fail_count, load_partial_count_parse_failed = _meta_int_state(meta, _DOWNTIME_META_KEYS["load_partial_count"])
    extend_partial_fail_count, extend_partial_count_parse_failed = _meta_int_state(meta, _DOWNTIME_META_KEYS["extend_partial_count"])
    downtime_extend_attempted, downtime_extend_attempted_parse_failed = _meta_bool_state(
        meta, _DOWNTIME_META_KEYS["extend_attempted"], default=False
    )
    downtime_extend_ok, downtime_extend_ok_parse_failed = _meta_bool_state(meta, _DOWNTIME_META_KEYS["extend_ok"], default=True)
    return {
        "downtime_load_ok": downtime_load_ok,
        "load_partial_fail_count": load_partial_fail_count,
        "extend_partial_fail_count": extend_partial_fail_count,
        "downtime_extend_attempted": downtime_extend_attempted,
        "downtime_extend_ok": downtime_extend_ok,
        "meta_parse_failed": bool(
            load_partial_count_parse_failed
            or extend_partial_count_parse_failed
            or downtime_load_ok_parse_failed
            or downtime_extend_attempted_parse_failed
            or downtime_extend_ok_parse_failed
        ),
        "load_partial_sample": _meta_sample(meta, _DOWNTIME_META_KEYS["load_partial_sample"]),
        "extend_partial_sample": _meta_sample(meta, _DOWNTIME_META_KEYS["extend_partial_sample"]),
    }


def _downtime_degraded_flags(state: Dict[str, Any], *, auto_assign_enabled: bool) -> Dict[str, bool]:
    load_failed = bool(not state["downtime_load_ok"])
    load_partial_failed = bool(state["load_partial_fail_count"] > 0 or state["meta_parse_failed"])
    extend_failed = bool(auto_assign_enabled and state["downtime_extend_attempted"] and (not state["downtime_extend_ok"]))
    extend_partial_failed = bool(
        auto_assign_enabled
        and state["downtime_extend_attempted"]
        and (state["extend_partial_fail_count"] > 0 or state["meta_parse_failed"])
    )
    return {
        "load_failed": load_failed,
        "load_partial_failed": load_partial_failed,
        "extend_failed": extend_failed,
        "extend_partial_failed": extend_partial_failed,
    }


def compute_downtime_degradation(cfg: Any, *, downtime_meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    snapshot = ensure_schedule_config_snapshot(
        cfg,
        strict_mode=False,
        source="scheduler.summary.downtime_degradation",
    )
    auto_assign_enabled = str(snapshot.auto_assign_enabled).strip().lower() == YesNo.YES.value
    meta = downtime_meta if isinstance(downtime_meta, dict) else {}
    state = _downtime_meta_state(meta)
    flags = _downtime_degraded_flags(state, auto_assign_enabled=bool(auto_assign_enabled))

    return {
        "auto_assign_enabled": bool(auto_assign_enabled),
        "downtime_load_ok": bool(state["downtime_load_ok"]),
        "downtime_degraded": bool(
            flags["load_failed"]
            or flags["load_partial_failed"]
            or flags["extend_failed"]
            or flags["extend_partial_failed"]
            or state["meta_parse_failed"]
        ),
        "downtime_degradation_reason": _downtime_reason(
            auto_assign_enabled=bool(auto_assign_enabled),
            downtime_extend_attempted=bool(state["downtime_extend_attempted"]),
            load_failed=bool(flags["load_failed"]),
            load_partial_fail_count=int(state["load_partial_fail_count"]),
            load_partial_fail_machines_sample=state["load_partial_sample"],
            extend_failed=bool(flags["extend_failed"]),
            extend_partial_fail_count=int(state["extend_partial_fail_count"]),
            extend_partial_fail_machines_sample=state["extend_partial_sample"],
            meta_parse_failed=bool(state["meta_parse_failed"]),
        ),
        "downtime_extend_attempted": bool(state["downtime_extend_attempted"]),
        "load_partial_fail_count": int(state["load_partial_fail_count"]),
        "load_partial_fail_machines_sample": state["load_partial_sample"],
        "extend_partial_fail_count": int(state["extend_partial_fail_count"]),
        "extend_partial_fail_machines_sample": state["extend_partial_sample"],
        "downtime_meta_parse_failed": bool(state["meta_parse_failed"]),
    }


__all__ = ["compute_downtime_degradation"]
