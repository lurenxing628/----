from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

# O23 KEEP: 本模块刻意保留为诊断合同事实记录/兼容面。
# 活页面的非有限数字 loud-raise 护栏在 web.viewmodels.scheduler_analysis_diagnostic_helpers,
# 不要反向删除 web 孪生，也不要把活路径裸改指这里。


def _list_or_empty(value: Optional[Iterable[Any]]) -> List[Any]:
    if value is None:
        return []
    return list(value)


def build_diagnostic_link(
    *,
    label: str,
    url: str,
    kind: str = "",
) -> Dict[str, Any]:
    return {
        "label": str(label or ""),
        "url": str(url or ""),
        "kind": str(kind or ""),
    }


def build_diagnostic_item(
    *,
    key: str,
    label: str,
    value: Any = None,
    level: str = "unknown",
    message: str = "",
    details: Optional[Iterable[Any]] = None,
    links: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "key": str(key or ""),
        "label": str(label or ""),
        "value": value,
        "level": str(level or "unknown"),
        "message": str(message or ""),
        "details": _list_or_empty(details),
        "links": _list_or_empty(links),
    }


def build_diagnostic_section(
    *,
    key: str,
    title: str,
    status: str = "unknown",
    status_label: str = "",
    summary: str = "",
    items: Optional[Iterable[Dict[str, Any]]] = None,
    links: Optional[Iterable[Dict[str, Any]]] = None,
    degraded: bool = False,
    degradation_events: Optional[Iterable[Dict[str, Any]]] = None,
    empty_reason: str = "",
) -> Dict[str, Any]:
    return {
        "key": str(key or ""),
        "title": str(title or ""),
        "status": str(status or "unknown"),
        "status_label": str(status_label or ""),
        "summary": str(summary or ""),
        "items": _list_or_empty(items),
        "links": _list_or_empty(links),
        "degraded": bool(degraded),
        "degradation_events": _list_or_empty(degradation_events),
        "empty_reason": str(empty_reason or ""),
    }


def empty_diagnostic_sections() -> List[Dict[str, Any]]:
    return []


__all__ = [
    "build_diagnostic_item",
    "build_diagnostic_link",
    "build_diagnostic_section",
    "empty_diagnostic_sections",
]
