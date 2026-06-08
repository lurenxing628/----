from __future__ import annotations

from typing import Any, Dict, Optional

from core.services.common.degradation import DegradationCollector, DegradationEvent

from .gantt_critical_chain import _normalize_critical_chain_result, compute_critical_chain_from_rows


def _text(value: Any) -> str:
    return str(value or "").strip()


def plan_detail_filter_kwargs(
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    resource_type_text = _text(resource_type)
    resource_id_text = _text(resource_id)
    if resource_type_text or resource_id_text:
        filters["resource_type"] = resource_type_text
        filters["resource_id"] = resource_id_text
    batch_id_text = _text(batch_id)
    if batch_id_text:
        filters["batch_id"] = batch_id_text
    return filters


def critical_chain_for_plan_detail_filter(rows: Any, filters: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None
    raw = compute_critical_chain_from_rows([dict(row) for row in list(rows or [])])
    return _normalize_critical_chain_result(raw)


def collect_gantt_degradation_events(
    *,
    calendar_days_outcome: Any,
    tasks_outcome: Any,
    critical_chain: Dict[str, Any],
) -> DegradationCollector:
    collector = DegradationCollector()
    collector.extend(calendar_days_outcome.events)
    collector.extend(tasks_outcome.events)
    if critical_chain.get("available") is False:
        reason = _text(critical_chain.get("reason_code") or critical_chain.get("reason")) or "unknown"
        collector.add(
            DegradationEvent(
                code="critical_chain_unavailable",
                scope="scheduler.gantt",
                field="critical_chain",
                message=f"关键工序关系暂时看不了（reason={reason}）。",
            )
        )
    return collector


__all__ = [
    "collect_gantt_degradation_events",
    "critical_chain_for_plan_detail_filter",
    "plan_detail_filter_kwargs",
]
