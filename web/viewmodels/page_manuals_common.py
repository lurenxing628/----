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
            "- 先下载模板，保持第一个工作表和表头不变；系统只按模板里的列名认数据，不靠人猜。",
            "- 单次上传文件大小不超过 16MB。",
            "- 上传 Excel 后先检查。检查和预览只是在页面上把文件读一遍，不会写入数据库，也不会改掉原有资料。",
            "- 看完检查结果后，确认没有错误，也能接受被跳过的行，再执行正式写入。",
            "- 检查结果里还有错误时，不能确认写入；先按提示改 Excel，再重新上传检查。",
            "- 如果检查后又改了 Excel 文件，或页面提示文件已过期，就要重新上传并重新检查。这样做是为了避免“预览的是旧文件，写入的是另一个文件”。",
            "- 只有点了确认写入，系统才会真正改数据库。确认写入时如果又遇到问题，页面会提示失败原因；有的页面会整批回到写入前，有的页面会保留成功行，具体以页面提示为准。",
            "- 导入完成后建议再导出一次当前数据做复核。",
        ]
    ),
    "excel_check_result_meaning": "\n".join(
        [
            "- 检查结果是系统提前帮你看 Excel：哪些行准备新增，哪些行准备更新，哪些行不会写入，哪些行必须修改。",
            "- 新增：系统里原来没有这个编号，确认写入后会新建一条资料。",
            "- 更新：系统里已经有这个编号，确认写入后会按 Excel 里的新内容改掉原资料。",
            "- 无变化：系统里已有资料和 Excel 内容一样，普通导入时通常不会重复改；如果这次选的是“清空本类数据后重导”，检查阶段仍可能显示更新或无变化，但确认写入会先清空这一类旧数据，再按 Excel 文件重新建。",
            "- 跳过：这行不写入，但不一定是坏数据；常见原因是导入模式要求跳过已有编号，或这一行没有达到本次写入条件。",
            "- 错误：这行有必须先修的问题，例如必填项为空、编号找不到、日期不合法、数量不是正数。只要还有错误，就不能确认写入。",
        ]
    ),
    "excel_skip_vs_error": "\n".join(
        [
            "- 跳过：意思是“这行本次不处理”。它不会写进数据库，也不会挡住其他正确行继续写入。",
            "- 错误：意思是“这行不合规，必须先改”。有错误时，系统通常会阻止确认写入，避免把问题数据带进正式资料。",
            "- 如果你本来就是想只补新编号，已有编号被跳过是正常现象；如果你想修改已有资料，却看到它被跳过，就要检查导入模式是不是选错了。",
        ]
    ),
    "excel_recheck_before_confirm": "\n".join(
        [
            "- 检查结果只对应刚才上传的那一个文件。",
            "- 检查后只要改过 Excel、换过文件、刷新后页面提示预览已失效，就要重新上传检查。",
            "- 重新检查时，系统会重新按当前库数据和页面选项检查；如果当前库数据、导入模式、是否清空重导等检查条件变了，页面会要求重新检查。",
            "- 重新检查不是多此一举，而是为了保证页面上看到的新增、更新、跳过、错误，和最后确认写入时系统重新判断的结果一致。",
        ]
    ),
    "excel_write_result_meaning": "\n".join(
        [
            "- 导入完成：本次允许写入的内容已经写入数据库，页面通常会告诉你新增、更新、跳过、错误各有多少；预览里的“无变化”常会并入跳过，不一定单独显示。",
            "- 部分完成：有些内容已经写入，有些内容因为冲突或异常没有写入。先看页面给出的失败原因，再导出当前数据复核。",
            "- 被拒绝：系统没有写入这次数据。常见原因是检查结果还有错误、文件过期、清空重导风险没有确认，或写入时发现关键资料不对。",
            "- 不管是哪一种结果，确认写入后如果要继续排产或继续维护，建议先回列表页或导出文件核对一次。",
        ]
    ),
    "excel_import_modes": "\n".join(
        [
            "- 更新已有，新增缺少：编号相同的会按 Excel 内容更新，系统里没有的编号会新增。适合用同一张表修正资料；风险是旧资料会被新表覆盖，确认前要看清哪些行会更新。",
            "- 只导入新编号：系统里已经有的编号会跳过，只补系统里没有的新编号。适合只追加新订单、新人员、新设备；风险是你想改旧资料时不会生效。",
            "- 清空本类数据后重导：检查阶段仍可能显示更新或无变化，但确认写入不是“不动旧数据”；它会先删除这一类旧数据，再按 Excel 文件重新建立。风险最高，可能连带影响排产记录、工序补充或关联关系；使用前必须确认引用关系，并先做备份。",
            "- 不确定选哪个时，先用“更新已有，新增缺少”做检查预览，看清楚会新增、更新、跳过哪些行，再决定是否确认写入。",
        ]
    ),
    "excel_date_format": "\n".join(
        [
            "- 优先使用 `2026-04-15` 或 `2026/04/15` 这种日期格式。",
            "- Excel 日期单元格通常也能识别，但导出回填前要先预览结果。",
            "- 时间建议统一写成 `08:00` 这种 24 小时格式。",
            "- 不要把交期、齐套日期、停机日期写成“下周三”“月底前”这类口头说法，系统无法稳定识别。",
        ]
    ),
    "excel_common_errors": "\n".join(
        [
            "- 表头被改名或删列，是最常见的导入失败原因（列顺序可以不同，不影响导入）。",
            "- 被引用的数据不存在时，导入会直接报错，例如人员不存在却先导关联表。",
            "- 填了系统不认识的固定选项，系统会提示错误，不会自己猜。",
            "- 数量、工时、周期这类数字如果填成文字、负数、空值或无穷大，通常会被拒绝。",
            "- 编号前后多了空格、全角符号或被 Excel 吃掉前导零，也可能导致系统找不到原资料。",
        ]
    ),
    "excel_format_warning": "\n".join(
        [
            "- 只改数据行，不要改第一个工作表名称、表头文字和必填列；系统主要按第一个工作表和表头读数据。",
            '- 编号类的列建议在 Excel 中设为"文本"格式再填写，否则前导零（如 001、B001）可能会丢失或变形。',
            "- 数量、工时、周期、效率这类列要填普通数字；不要填“约 10 件”“半天”“很多”这类文字。",
            "- 是/否类字段（如主操设备、允许普通件、允许急件）建议填 是/否；以前文件里写过 1/0 的，不用先手工改，系统会尽量读懂。",
            "- 下载的模板和导出回填中，选项类字段建议填写中文值；新文件请按页面写的中文选项填写。",
            "- 复制粘贴后要留意隐藏空格和合并单元格。看起来在同一格里的内容，系统不一定能按你看到的样子读出来。",
        ]
    ),
    "excel_strict_mode_basics": "\n".join(
        [
            "- 严格模式可以理解成“资料不完整就先停下”。适合正式导入、正式排产前使用，宁愿现在报错，也不要把不确定的数据带进后面。",
            "- 不开严格模式时，系统会尽量把能确认的数据先处理完；遇到可补的小问题，可能会先按默认值继续，并用提醒告诉你之后要补。",
            "- 严格模式不是让系统算得更快，也不是让系统自动修资料；它只是把有风险的地方更早拦下来。",
            "- 批次、图号、数量、日期这类必须正确的内容，不管开不开严格模式，错了都要先改。",
        ]
    ),
    "excel_preview_write_boundary": "\n".join(
        [
            "- 预览页只是给你核对，不会写库。",
            "- 预览里看到“准备新增/准备更新”，意思是确认写入后才会发生，不是已经写进去了。",
            "- 离开预览页、换文件、改 Excel 后，之前的预览就不能再当准，要重新上传检查。",
        ]
    ),
    "list_page_basics": "\n".join(
        [
            "- 先用筛选缩小范围，再进行编辑、删除或批量操作。",
            "- 列表页通常承担入口作用：新增、详情、批量维护等操作都从这里分流。",
            "- 做批量操作前，先确认当前筛选条件与已选记录数量。",
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
            "- 建议把备份文件按日期和用途命名，方便以后找回和核对。",
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
