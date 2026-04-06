from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    version: int
    week_start: str
    week_end: str
    task_count: int
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    calendar_days: List[Dict[str, Any]] = field(default_factory=list)
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
            "version": int(self.version),
            "week_start": str(self.week_start or ""),
            "week_end": str(self.week_end or ""),
            "task_count": int(self.task_count),
            "tasks": list(self.tasks or []),
            "calendar_days": list(self.calendar_days or []),
            "critical_chain": dict(self.critical_chain or {}),
            "degraded": bool(self.degraded),
            "degradation_events": list(self.degradation_events or []),
            "degradation_counters": dict(self.degradation_counters or {}),
            "empty_reason": self.empty_reason,
            "overdue_markers_degraded": bool(self.overdue_markers_degraded),
            "overdue_markers_partial": bool(self.overdue_markers_partial),
            "overdue_markers_message": str(self.overdue_markers_message or ""),
        }
        if include_history:
            out["history"] = dict(self.history) if isinstance(self.history, dict) else None
        return out


def build_gantt_contract(
    *,
    contract_version: int,
    view: str,
    version: int,
    week_start: str,
    week_end: str,
    tasks: List[Dict[str, Any]],
    calendar_days: List[Dict[str, Any]],
    critical_chain: Dict[str, Any],
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
        version=int(version),
        week_start=str(week_start or ""),
        week_end=str(week_end or ""),
        task_count=len(tasks or []),
        tasks=list(tasks or []),
        calendar_days=list(calendar_days or []),
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
