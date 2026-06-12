from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.services.scheduler.degradation_messages import public_degradation_events

_CRITICAL_REASON_LABELS = {
    "calc_exception": "关键工序关系计算异常",
    "repo_exception": "关键工序关系计算异常",
    "rows_exception": "关键工序关系计算异常",
    "rows_load_exception": "关键工序关系资料读取异常",
    "no_history": "暂无排产历史，关键工序关系暂时看不了",
    "unknown": "关键工序关系暂时看不了",
}
_ALLOWED_CRITICAL_REASON_CODES = frozenset(_CRITICAL_REASON_LABELS)


def _public_dropped_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _public_critical_chain(chain: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(chain or {})
    # R55：scope 标记对外永远在场——只有计划明细筛选路径（critical_chain_for_plan_detail_filter）
    # 显式标 filtered，其余整版口径（provider/候选/空版本）缺省 full，供前端区分 makespan 是否筛选口径。
    scope = "filtered" if str(raw.get("scope") or "").strip() == "filtered" else "full"
    reason = str(raw.get("reason") or "").strip()
    if bool(raw.get("available") is False):
        dropped_count = _public_dropped_count(raw.get("dropped_count"))
        out = {
            "available": False,
            "ids": [],
            "edges": [],
            "edge_count": 0,
            "edge_type_stats": {},
            "dropped_count": dropped_count,
            "critical_chain_partial": bool(raw.get("critical_chain_partial")) or dropped_count > 0,
            "scope": scope,
        }
        if "cache_hit" in raw:
            out["cache_hit"] = bool(raw.get("cache_hit"))
        reason_code = str(raw.get("reason_code") or reason or "unknown").strip().lower() or "unknown"
        if reason_code not in _ALLOWED_CRITICAL_REASON_CODES:
            reason_code = "unknown"
        out["reason_code"] = reason_code
        out["reason"] = _CRITICAL_REASON_LABELS.get(reason_code) or (
            "关键工序关系暂时看不了" if reason and reason.isascii() else reason
        )
        return out
    raw["scope"] = scope
    return raw


def _public_history(history: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(history, dict):
        return None
    out = dict(history)
    out.pop("result_summary", None)
    return out


@dataclass
class GanttContractDTO:
    """
    甘特图统一数据契约（Web/PyQt 共用）。

    说明：
    - history 默认不下发，按 include_history 控制，降低接口体积。
    - 字段顺序固定，便于快照测试和跨端对齐。
    """

    contract_version: int
    view: str
    version: Optional[int]
    week_start: str
    week_end: str
    task_count: int
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    calendar_days: List[Dict[str, Any]] = field(default_factory=list)
    resource_load: List[Dict[str, Any]] = field(default_factory=list)
    critical_chain: Dict[str, Any] = field(default_factory=dict)
    degraded: bool = False
    degradation_events: List[Dict[str, Any]] = field(default_factory=list)
    degradation_counters: Dict[str, int] = field(default_factory=dict)
    empty_reason: Optional[str] = None
    overdue_markers_degraded: bool = False
    overdue_markers_partial: bool = False
    overdue_markers_message: str = ""
    history: Optional[Dict[str, Any]] = None

    def to_dict(self, *, include_history: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "contract_version": int(self.contract_version),
            "view": str(self.view or "machine"),
            "version": int(self.version) if self.version is not None else None,
            "week_start": str(self.week_start or ""),
            "week_end": str(self.week_end or ""),
            "task_count": int(self.task_count),
            "tasks": list(self.tasks or []),
            "calendar_days": list(self.calendar_days or []),
            "resource_load": list(self.resource_load or []),
            "critical_chain": _public_critical_chain(self.critical_chain or {}),
            "degraded": bool(self.degraded),
            "degradation_events": public_degradation_events(self.degradation_events or []),
            "degradation_counters": dict(self.degradation_counters or {}),
            "empty_reason": self.empty_reason,
            "overdue_markers_degraded": bool(self.overdue_markers_degraded),
            "overdue_markers_partial": bool(self.overdue_markers_partial),
            "overdue_markers_message": str(self.overdue_markers_message or ""),
        }
        if include_history:
            out["history"] = _public_history(self.history)
        return out


def build_gantt_contract(
    *,
    contract_version: int,
    view: str,
    version: Optional[int],
    week_start: str,
    week_end: str,
    tasks: List[Dict[str, Any]],
    calendar_days: List[Dict[str, Any]],
    critical_chain: Dict[str, Any],
    resource_load: Optional[List[Dict[str, Any]]] = None,
    degraded: bool = False,
    degradation_events: Optional[List[Dict[str, Any]]] = None,
    degradation_counters: Optional[Dict[str, int]] = None,
    empty_reason: Optional[str] = None,
    overdue_markers_degraded: bool = False,
    overdue_markers_partial: bool = False,
    overdue_markers_message: str = "",
    include_history: bool = False,
    history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dto = GanttContractDTO(
        contract_version=int(contract_version),
        view=str(view or "machine"),
        version=int(version) if version is not None else None,
        week_start=str(week_start or ""),
        week_end=str(week_end or ""),
        task_count=len(tasks or []),
        tasks=list(tasks or []),
        calendar_days=list(calendar_days or []),
        resource_load=list(resource_load or []),
        critical_chain=dict(critical_chain or {}),
        degraded=bool(degraded),
        degradation_events=list(degradation_events or []),
        degradation_counters=dict(degradation_counters or {}),
        empty_reason=empty_reason,
        overdue_markers_degraded=bool(overdue_markers_degraded),
        overdue_markers_partial=bool(overdue_markers_partial),
        overdue_markers_message=str(overdue_markers_message or ""),
        history=dict(history or {}) if isinstance(history, dict) else None,
    )
    return dto.to_dict(include_history=bool(include_history))
