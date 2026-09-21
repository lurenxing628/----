from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional


def _card(title: str, *items: str) -> Dict[str, Any]:
    return {
        "title": title,
        "items": [str(item).strip() for item in items if str(item).strip()],
    }


def _section(title: str, body_md: str) -> Dict[str, str]:
    return {
        "title": str(title).strip(),
        "body_md": str(body_md).strip(),
    }


def _topic(
    title: str,
    summary: str,
    full_manual_anchor: str,
    sections: List[Dict[str, str]],
    related_manual_ids: List[str],
    help_card: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "title": str(title).strip(),
        "summary": str(summary).strip(),
        "full_manual_anchor": str(full_manual_anchor).strip(),
        "sections": sections,
        "related_manual_ids": [str(item).strip() for item in related_manual_ids if str(item).strip()],
    }
    if help_card:
        data["help_card"] = help_card
    return data


SHARED_FRAGMENTS: Dict[str, str] = {
    "list_page_basics": "\n".join(
        [
            "- 需要找少量记录时，可以用筛选或翻页缩小范围（具体筛选方式因页面而异，有些页面有搜索框和下拉筛选，有些只有翻页）；只是新增资料、进入详情或打开批量维护时，不必先筛选。",
            "- 列表页通常承担入口作用：新增、详情、批量维护等操作都从这里分流，具体以页面按钮为准。",
            "- 做批量操作前，先确认当前筛选条件；如果页面支持勾选多条记录，再核对已选记录数量。没有勾选区的页面，就按页面上的单行按钮或表单按钮处理。",
        ]
    ),
    "scheduler_version_basics": "\n".join(
        [
            "- 执行排产会推动批次状态，模拟排产只生成新版本，不改状态。",
            "- 查看结果时先确认版本号，再比较指标、甘特图和周计划。",
            "- 不指定版本时，系统会查看最新排产历史；手动指定不存在的版本会提示该版本不存在，不会偷偷切回最新版本。",
            "- 回看历史版本时，要区分“当前生产依据”与“历史模拟方案”。",
        ]
    ),
    "reports_filter_basics": "\n".join(
        [
            "- 报表页优先按时间范围、版本、资源或状态缩小范围。",
            "- 先看汇总指标，再下钻具体明细，排查效率更高。",
            "- 报表结果通常依赖版本、排程记录和资源日历，先确认源数据是否最新。",
        ]
    ),
    "backup_risk_basics": "\n".join(
        [
            "- 备份和恢复都属于高风险操作，执行前先确认当前数据库路径与目标文件。",
            "- 恢复会覆盖现有数据；系统会在恢复前自动生成一份“恢复前自动备份”，方便恢复到操作前。",
            "- 如果恢复过程失败，系统会尽最大努力自动恢复到操作前的备份，但仍建议重要操作前手动留一份备份。",
            "- 备份文件名由系统按时间和用途自动生成，恢复前主要核对文件名里的时间、用途后缀、页面创建时间和文件大小。",
        ]
    ),
}


def _expand_fragments(text: str) -> str:
    result = str(text or "")
    for key, value in SHARED_FRAGMENTS.items():
        result = result.replace("{{" + key + "}}", value)
    return result.strip()


def _build_full_manual_label(anchor: str) -> str:
    raw = str(anchor or "").strip().lstrip("#").strip()
    if not raw:
        return ""
    idx = 0
    while idx < len(raw) and (raw[idx].isdigit() or raw[idx] == "-"):
        idx += 1
    if 0 < idx < len(raw):
        prefix = ".".join([part for part in raw[:idx].strip("-").split("-") if part])
        suffix = raw[idx:].strip()
        if prefix and suffix:
            return f"{prefix} {suffix}"
    return raw


def _clone_help_card(card: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not card:
        return None
    title = str(card.get("title") or "").strip()
    items = [str(item).strip() for item in (card.get("items") or []) if str(item).strip()]
    if not title or not items:
        return None
    return {"title": title, "items": items}


def _clone_sections(sections: List[Mapping[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for section in sections or []:
        title = str(section.get("title") or "").strip()
        body_md = _expand_fragments(str(section.get("body_md") or ""))
        if title and body_md:
            out.append({"title": title, "body_md": body_md})
    return out


def _clean_related_ids(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items or []:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _apply_payload_overrides(payload: Dict[str, Any], overrides: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    extra = deepcopy(dict(overrides or {}))
    if extra.get("summary"):
        payload["summary"] = str(extra.get("summary") or "").strip()
    if "help_card" in extra:
        payload["help_card"] = _clone_help_card(extra.get("help_card"))
    if "related_manual_ids" in extra:
        payload["related_manual_ids"] = _clean_related_ids(list(extra.get("related_manual_ids") or []))
    return payload


def build_manual_payload_from_topic(
    manual_id: str,
    topic: Mapping[str, Any],
    overrides: Optional[Mapping[str, Any]] = None,
    include_sections: bool = True,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "manual_id": str(manual_id).strip(),
        "title": str(topic.get("title") or "").strip(),
        "summary": str(topic.get("summary") or "").strip(),
        "full_manual_anchor": str(topic.get("full_manual_anchor") or "").strip(),
        "full_manual_label": _build_full_manual_label(str(topic.get("full_manual_anchor") or "").strip()),
        "help_card": _clone_help_card(topic.get("help_card")),
        "related_manual_ids": _clean_related_ids(list(topic.get("related_manual_ids") or [])),
    }
    if include_sections:
        payload["sections"] = _clone_sections(list(topic.get("sections") or []))
    return _apply_payload_overrides(payload, overrides)


def build_page_fallback_text_from_bundle(bundle: Optional[Dict[str, Any]]) -> str:
    if not bundle:
        return ""

    current = bundle["current_manual"]
    related = bundle["related_manuals"]
    lines: List[str] = [f"## {current['title']}", "", current.get("summary") or "", ""]
    for section in current.get("sections") or []:
        lines.extend([f"### {section['title']}", "", section["body_md"], ""])
    if related:
        lines.extend(["## 相关模块说明", ""])
        for item in related:
            lines.extend([f"### {item['title']}", "", item.get("summary") or "", ""])
            for section in item.get("preview_sections") or []:
                lines.extend([f"#### {section['title']}", "", section["body_md"], ""])
    return "\n".join(lines).strip()
