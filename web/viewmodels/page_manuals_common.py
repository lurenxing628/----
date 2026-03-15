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
    "excel_common_flow": "\n".join(
        [
            "- 先下载模板，保持首个工作表和表头不变。",
            "- 上传后先预览，确认没有错误或跳过风险，再执行正式导入。",
            "- 只要有 1 行处于错误状态，整份文件都不会导入。",
            "- 导入完成后建议再导出一次当前数据做复核。",
        ]
    ),
    "excel_import_modes": "\n".join(
        [
            "- 覆盖：相同主键更新，不存在的新增。",
            "- 追加：已存在的数据跳过，只补新数据。",
            "- 替换：先清空再导入，风险最高，使用前必须确认引用关系和备份。",
        ]
    ),
    "excel_date_format": "\n".join(
        [
            "- 优先使用 `2026-04-15` 或 `2026/04/15` 这种日期格式。",
            "- Excel 日期单元格通常也能识别，但导出回填前要先预览结果。",
            "- 时间建议统一写成 `08:00` 这种 24 小时格式。",
        ]
    ),
    "excel_common_errors": "\n".join(
        [
            "- 表头被改名、删列或换顺序，是最常见的导入失败原因。",
            "- 被引用的数据不存在时，导入会直接报错，例如人员不存在却先导关联表。",
            "- 文本列写成不受支持的枚举词，系统会拒绝导入而不是自动猜测。",
        ]
    ),
    "list_page_basics": "\n".join(
        [
            "- 先用筛选缩小范围，再进行编辑、删除或批量操作。",
            "- 列表页通常承担入口作用：新增、详情、导入导出都从这里分流。",
            "- 做批量操作前，先确认当前筛选条件与已选记录数量。",
        ]
    ),
    "scheduler_version_basics": "\n".join(
        [
            "- 执行排产会推动批次状态，模拟排产只生成新版本，不改状态。",
            "- 查看结果时先确认版本号，再比较指标、甘特图和周计划。",
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
            "- 恢复会覆盖现有数据，正式恢复前应先做一次当前库备份。",
            "- 建议把备份文件按日期和用途命名，方便回滚和审计。",
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
