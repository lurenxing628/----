from __future__ import annotations

from typing import Any, Dict, Optional

from core.services.common.degradation import DegradationCollector, DegradationEvent

from .gantt_critical_chain import _normalize_critical_chain_result, compute_critical_chain_from_rows
from .resource_dispatch_support import extract_overdue_batch_ids_with_meta


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
    result = _normalize_critical_chain_result(raw)
    # R55：本路径把周窗口+资源/批次子集喂给整版算法，makespan/关键链是"筛选口径"，须显式标 scope=filtered，
    # 避免对外被当整版口径误读（呈现失真）。整版口径在 _public_critical_chain 缺省落 full。严禁裸删过滤。
    if isinstance(result, dict):
        result["scope"] = "filtered"
    return result


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


def log_overdue_marker_degraded(logger: Any, *, version: int, reason: str, message: str) -> None:
    if logger is None:
        return
    logger.warning(
        "甘特图超期标记降级（service=GanttService, page=gantt, version=%s, source=%s, message=%s）",
        version,
        reason or "unknown",
        message or "",
    )


def log_overdue_marker_partial(logger: Any, *, version: int, reason: str, message: str) -> None:
    if logger is None:
        return
    logger.warning(
        "甘特图超期标记部分不完整（service=GanttService, page=gantt, version=%s, source=%s, message=%s）",
        version,
        reason or "unknown",
        message or "",
    )


def overdue_batch_ids_from_history_meta(history_repo: Any, logger: Any, version: int) -> Dict[str, Any]:
    hist = history_repo.get_by_version(int(version))
    if not hist:
        meta = {
            "ids": [],
            "degraded": True,
            "partial": False,
            "message": "排产历史缺失，超期标记可能不完整。",
            "reason": "history_missing",
        }
        log_overdue_marker_degraded(logger, version=int(version), reason=str(meta["reason"]), message=str(meta["message"]))
        return meta

    meta = extract_overdue_batch_ids_with_meta(hist.result_summary)
    if meta.get("degraded"):
        log_overdue_marker_degraded(
            logger, version=int(version), reason=str(meta.get("reason") or "unknown"), message=str(meta.get("message") or "")
        )
    elif meta.get("partial"):
        log_overdue_marker_partial(
            logger, version=int(version), reason=str(meta.get("reason") or "unknown"), message=str(meta.get("message") or "")
        )
    return meta


__all__ = [
    "collect_gantt_degradation_events",
    "critical_chain_for_plan_detail_filter",
    "log_overdue_marker_degraded",
    "log_overdue_marker_partial",
    "overdue_batch_ids_from_history_meta",
    "plan_detail_filter_kwargs",
]
