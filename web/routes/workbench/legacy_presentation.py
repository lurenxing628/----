"""Public fields, rendered manual blocks and anchors; never dump arbitrary row data."""

import html
import re

from core.services.common.excel_template_defaults import get_default_templates

_RESULT_TEMPLATES = {
    "excel_demo": "人员基本信息.xlsx",
    "personnel.excel_link": "人员设备关联.xlsx",
    "personnel.excel_operator_calendar": "人员专属工作日历.xlsx",
    "personnel.excel_operator": "人员基本信息.xlsx",
    "equipment.excel_link": "设备人员关联.xlsx",
    "equipment.excel_machine": "设备信息.xlsx",
    "process.excel_op_type": "工种配置.xlsx",
    "process.excel_part_op_hours": "零件工序工时.xlsx",
    "process.excel_routes": "零件工艺路线.xlsx",
    "process.excel_supplier": "供应商配置.xlsx",
    "scheduler.excel_batches": "批次信息.xlsx",
    "scheduler.excel_calendar": "工作日历.xlsx",
}
RESULT_ENDPOINTS = {prefix + separator + suffix: filename
                    for prefix, filename in _RESULT_TEMPLATES.items()
                    for separator in ("." if prefix == "excel_demo" else "_",)
                    for suffix in ("preview", "confirm")}


def _public_scalar(value):
    if value is None:
        return ""
    if type(value) in (str, int, float, bool):
        return str(value)
    return "这一项不是能直接显示的单个值，请核对原文件。"


def preview_fields(row, endpoint):
    filename = RESULT_ENDPOINTS.get(endpoint)
    if filename is None:
        raise ValueError("Legacy result endpoint has no approved public template fields.")
    definition = next(item for item in get_default_templates() if item["filename"] == filename)
    headers = list(definition["headers"])
    for aliases in definition.get("legacy_headers", ()):
        headers.extend(key for key in aliases if key not in headers)
    data = getattr(row, "display_data", getattr(row, "data", {})) or {}
    changes = getattr(row, "display_changes", getattr(row, "changes", {})) or {}
    fields = []
    for key in headers:
        if key not in data and key not in changes:
            continue
        item = {"label": key, "value": _public_scalar(data.get(key)), "changed": key in changes}
        if key in changes:
            pair = changes[key]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("Legacy field change must retain its before/after pair.")
            item.update(before=_public_scalar(pair[0]), after=_public_scalar(pair[1]))
        fields.append(item)
    return fields


_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE_SPAN = re.compile(r"(`[^`]+`)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_THEMATIC = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_FENCE = "```"


def _inline(text):
    """Escape the public text first, then keep only bold and inline code."""
    parts = _CODE_SPAN.split(html.escape(text))
    for index, part in enumerate(parts):
        if len(part) > 2 and part.startswith("`") and part.endswith("`"):
            parts[index] = "<code>" + part[1:-1] + "</code>"
        else:
            parts[index] = _BOLD.sub(r"<strong>\1</strong>", part)
    return "".join(parts)


def _cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_html(rows):
    head = "".join("<th scope=\"col\">" + _inline(cell) + "</th>" for cell in _cells(rows[0]))
    body = "".join("<tr>" + "".join("<td>" + _inline(cell) + "</td>" for cell in _cells(row)) + "</tr>"
                   for row in rows[2:])
    return "<div class=\"manual-table\"><table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table></div>"


def _list_html(lines, start, pattern, tag):
    items, index = [], start
    while index < len(lines):
        match = pattern.match(lines[index])
        if not match:
            break
        items.append("<li>" + _inline(match.group(1)) + "</li>")
        index += 1
    return "<" + tag + ">" + "".join(items) + "</" + tag + ">", index


def _block_start(line):
    return bool(_TABLE_ROW.match(line) or _BULLET.match(line) or _ORDERED.match(line)
                or _QUOTE.match(line) or _THEMATIC.match(line) or line.strip().startswith(_FENCE))


def _fence_html(lines, index):
    index += 1
    code = []
    while index < len(lines) and not lines[index].strip().startswith(_FENCE):
        code.append(lines[index])
        index += 1
    return "<pre class=\"manual-code\"><code>" + html.escape("\n".join(code)) + "</code></pre>", index + 1


def _table_start(lines, index):
    return bool(_TABLE_ROW.match(lines[index]) and index + 1 < len(lines) and _TABLE_RULE.match(lines[index + 1]))


def _table_block(lines, index):
    rows = [lines[index], lines[index + 1]]
    index += 2
    while index < len(lines) and _TABLE_ROW.match(lines[index]):
        rows.append(lines[index])
        index += 1
    return _table_html(rows), index


def _quote_html(lines, index):
    quoted = []
    while index < len(lines):
        match = _QUOTE.match(lines[index])
        if match is None:
            break
        quoted.append(match.group(1).strip())
        index += 1
    return "<blockquote><p>" + _inline("".join(quoted)) + "</p></blockquote>", index


def _paragraph_html(lines, index):
    paragraph = []
    while index < len(lines) and lines[index].strip() and not _block_start(lines[index]):
        paragraph.append(lines[index].strip())
        index += 1
    return "<p>" + _inline("".join(paragraph)) + "</p>", index


def _block_html(lines, index):
    """Render the block that starts at ``index``; returns (html, next_index). Blank lines render nothing."""
    line = lines[index]
    if line.strip().startswith(_FENCE):
        return _fence_html(lines, index)
    if not line.strip():
        return "", index + 1
    if _THEMATIC.match(line):
        return "<hr>", index + 1
    if _table_start(lines, index):
        return _table_block(lines, index)
    if _BULLET.match(line):
        return _list_html(lines, index, _BULLET, "ul")
    if _ORDERED.match(line):
        return _list_html(lines, index, _ORDERED, "ol")
    if _QUOTE.match(line):
        return _quote_html(lines, index)
    return _paragraph_html(lines, index)


def render_manual_markdown(text):
    """Turn the retained manual text into safe HTML: no raw source symbols on screen.

    Only the subset the manual actually uses is converted; links stay literal text
    so no href can be produced from the source file.
    """
    lines = text.split("\n")
    out, index = [], 0
    while index < len(lines):
        chunk, index = _block_html(lines, index)
        if chunk:
            out.append(chunk)
    return "".join(out)


def manual_outline(blocks):
    """Group the anchors by heading level so the reader sees chapters, not one long row."""
    outline = []
    for block in blocks:
        if not block.get("anchor"):
            continue
        entry = {"title": block["title"], "anchor": block["anchor"], "children": []}
        if block.get("level", 2) > 2 and outline:
            outline[-1]["children"].append(entry)
        else:
            outline.append(entry)
    return outline


def _heading_anchor(text):
    # Keep anchors generated by the former manual's slugifyHeading contract.
    text = re.sub(r"`([^`]+)`", r"\1", text.strip())
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^([0-9]+)\s*[.．。]\s*", r"\1-", text).lower()
    text = re.sub(r"[^a-z0-9_\u4e00-\u9fa5-]+", "", text)
    return re.sub(r"-+", "-", text).strip("-") or "section"


def _closed_block(title, anchor, level, body, source):
    text = "".join(body)
    return {"title": title, "anchor": anchor, "level": level, "body": text,
            "html": render_manual_markdown(text), "source": "".join(source)}


def manual_blocks(text):
    if not isinstance(text, str):
        raise ValueError("Manual source must be the existing public text.")
    blocks, body, title, anchor, source, fenced = [], [], "", "", [], False
    level = 0
    used = {}
    for line in text.splitlines(keepends=True):
        if line.strip().startswith(_FENCE):
            fenced = not fenced
        match = None if fenced else re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if source:
                blocks.append(_closed_block(title, anchor, level, body, source))
            title = match.group(2)
            level = len(match.group(1))
            base = _heading_anchor(title)
            used[base] = used.get(base, 0) + 1
            anchor = base if used[base] == 1 else base + "-" + str(used[base])
            body, source = [], [line]
        else:
            body.append(line)
            source.append(line)
    if source:
        blocks.append(_closed_block(title, anchor, level, body, source))
    return blocks


def install_legacy_presentation(app):
    filters = {"legacy_preview_fields": preview_fields, "legacy_manual_blocks": manual_blocks,
               "legacy_manual_outline": manual_outline, "legacy_manual_markdown": render_manual_markdown}
    if any(name in app.jinja_env.filters and app.jinja_env.filters[name] is not fn for name, fn in filters.items()):
        raise RuntimeError("Legacy presentation filter is already bound to another implementation.")
    app.jinja_env.filters.update(filters)
