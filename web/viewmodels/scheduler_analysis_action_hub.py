from __future__ import annotations

from typing import Any, Dict, List, Optional

_NEXT_LINK_ORDER = (
    ("gantt", "设备甘特图"),
    ("gantt", "人员甘特图"),
    ("resource_dispatch", "资源排班"),
    ("overdue_report", "超期清单"),
)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tone_class(status: Any) -> str:
    value = _text(status).lower()
    if value in ("danger", "error"):
        return "aps-summary-item-danger"
    if value == "warning":
        return "aps-summary-item-warning"
    if value == "ok":
        return "aps-summary-item-success"
    if value in ("notice", "empty", "unknown"):
        return "aps-summary-item-info"
    return "aps-summary-item-neutral"


def _row_for_next_links(display: Dict[str, Any]) -> Dict[str, Any]:
    rows = [row for row in _safe_list(display.get("rows")) if isinstance(row, dict)]
    for row in rows:
        if bool(row.get("is_adopted")):
            return row
    return rows[0] if rows else {}


def _ordered_next_links(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    links = [link for link in _safe_list(row.get("links")) if isinstance(link, dict)]
    ordered: List[Dict[str, Any]] = []
    used = set()
    for target_page, label in _NEXT_LINK_ORDER:
        for index, link in enumerate(links):
            if index in used:
                continue
            if _text(link.get("target_page")) == target_page and _text(link.get("label")) == label:
                ordered.append(link)
                used.add(index)
                break
    return ordered


def _candidate_notice(display: Dict[str, Any]) -> str:
    notice = _text(display.get("notice"))
    if notice:
        return notice
    if not bool(display.get("has_comparison")):
        return "本次没有可展示的候选方案对比，先查看诊断和排产指标。"
    return ""


def _candidate_status_messages(display: Dict[str, Any]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    for raw in _safe_list(display.get("status_messages")):
        if not isinstance(raw, dict):
            continue
        text = _text(raw.get("text"))
        if not text:
            continue
        class_name = _text(raw.get("class_name")) or "flash-card"
        messages.append({"class_name": class_name, "text": text})
    return messages


def _diagnostic_item_summary(section: Dict[str, Any]) -> Dict[str, str]:
    items = [item for item in _safe_list(section.get("items")) if isinstance(item, dict)]
    preferred = None
    for item in items:
        if _text(item.get("level")).lower() in ("danger", "error", "warning", "unknown", "notice"):
            preferred = item
            break
    item = preferred or (items[0] if items else {})
    return {
        "label": _text(item.get("label")),
        "value": _text(item.get("value")),
        "message": _text(item.get("message")),
    }


def _diagnostic_links(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for raw in _safe_list(section.get("links")):
        if isinstance(raw, dict) and _text(raw.get("label")) and _text(raw.get("url")):
            links.append(raw)
    for item in _safe_list(section.get("items")):
        if not isinstance(item, dict):
            continue
        for raw in _safe_list(item.get("links")):
            if isinstance(raw, dict) and _text(raw.get("label")) and _text(raw.get("url")):
                links.append(raw)
    return links[:2]


def _diagnostic_cards(diagnostic_sections: Any) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for raw in _safe_list(diagnostic_sections):
        section = _safe_dict(raw)
        title = _text(section.get("title"))
        if not title:
            continue
        item = _diagnostic_item_summary(section)
        summary = _text(section.get("summary"))
        if not summary:
            summary = _text(section.get("empty_reason")) or "暂时不能判断，请先结合排产指标查看。"
        cards.append(
            {
                "title": title,
                "status_label": _text(section.get("status_label")),
                "summary": summary,
                "item_label": item.get("label") or "诊断结果",
                "item_value": item.get("value") or "暂时不能判断",
                "item_message": item.get("message") or "",
                "tone_class": _tone_class(section.get("status")),
                "links": _diagnostic_links(section),
                "degraded": bool(section.get("degraded")),
            }
        )
    return cards[:4]


def build_analysis_action_hub(
    candidate_comparison_display: Optional[Dict[str, Any]],
    diagnostic_sections: Any,
) -> Dict[str, Any]:
    display = _safe_dict(candidate_comparison_display)
    row = _row_for_next_links(display)
    next_links = _ordered_next_links(row)
    notice = _candidate_notice(display)
    empty_state = ""
    if notice and not bool(display.get("has_comparison")):
        empty_state = notice
    if not next_links and _text(row.get("link_unavailable_reason")):
        empty_state = empty_state or _text(row.get("link_unavailable_reason"))

    summary_cards = [card for card in _safe_list(display.get("summary_cards")) if isinstance(card, dict)][:3]
    recommendation_card = display.get("recommendation_card") if isinstance(display.get("recommendation_card"), dict) else None
    diagnostic_cards = _diagnostic_cards(diagnostic_sections)
    return {
        "title": "排产分析行动入口",
        "subtitle": "本次排产的推荐结论、主要风险和后续查看入口。",
        "recommendation_card": recommendation_card,
        "summary_cards": summary_cards,
        "diagnostic_cards": diagnostic_cards,
        "next_links": next_links,
        "status_messages": _candidate_status_messages(display),
        "notice": notice,
        "empty_state": empty_state,
        "has_recommendation": recommendation_card is not None,
        "has_candidate_summary": bool(summary_cards),
        "has_diagnostics": bool(diagnostic_cards),
    }


__all__ = ["build_analysis_action_hub"]
