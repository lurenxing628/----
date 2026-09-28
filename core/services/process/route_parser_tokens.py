from __future__ import annotations

import re
from typing import List, Tuple

from core.models.process_route_text import serialize_route_rows as serialize_route_rows
from core.services.process.route_parser_errors import MISSING_START_SEQ_ERROR, missing_tail_op_error

# 需要移除的分隔符（空格、逗号、顿号、破折号、箭头等）
# 说明：
# - 文档/用户输入里常见 "->" / "→" / "-" / "—" 等分隔；若不移除 ">" 会污染工种名（如 "钳>"）。
# - 这里用“字符集合”覆盖：'-' 与 '>' 分别移除，即可兼容 "->"。
SEPARATORS = r"[\s,，、\-—–→>＞]+"
ROUTE_TOKEN_PATTERN = r"(\d+)([^\d]+)"
EXPLICIT_ROUTE_PREFIX = re.compile(r"[0-9０-９]+[ \t]*[:：]")


def compact_name_ambiguities(rows, names):
    numeric_names = {}
    for name in names:
        match = re.match(r"([0-9０-９]+)(.+)$", name)
        if match:
            prefix = match.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
            numeric_names.setdefault(match.group(2), []).append((prefix, name))
    issues = []
    for seq, name in rows:
        digits = str(seq).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        for prefix, registered in numeric_names.get(name, ()):
            remaining = digits[:-len(prefix)]
            if digits.endswith(prefix) and remaining and remaining.strip("0"):
                issues.append((seq, "工序号和数字开头的工种名可能混在一起，请加冒号明确“"
                               + remaining + ": " + registered + "”或“" + digits + ": " + name
                               + "”；原输入没有自动改写。"))
                break
    return issues


def _skip_route_space(text, cursor, *, horizontal=False):
    while cursor < len(text):
        if not (text[cursor] in " \t" if horizontal else text[cursor].isspace()):
            break
        cursor += 1
    return cursor


def _quoted_route_name(text, cursor):
    name = []
    while cursor < len(text):
        char = text[cursor]
        cursor += 1
        if char != '"':
            name.append(char)
        elif cursor < len(text) and text[cursor] == '"':
            name.append('"')
            cursor += 1
        else:
            cursor = _skip_route_space(text, cursor, horizontal=True)
            if cursor < len(text) and text[cursor] not in ";；\r\n":
                raise ValueError("工序名称后请用分号或换行分隔下一道工序。原输入已保留。")
            return "".join(name), cursor
    raise ValueError("工序名称的引号没有成对结束。请核对名称，原输入已保留。")


def _explicit_route_name(text, cursor):
    cursor = _skip_route_space(text, cursor, horizontal=True)
    if cursor < len(text) and text[cursor] == '"':
        return _quoted_route_name(text, cursor + 1)
    start = cursor
    while cursor < len(text) and text[cursor] not in ";；\r\n":
        cursor += 1
    name = text[start:cursor].strip()
    if '"' in name:
        raise ValueError("名称中的引号需要成对填写；也可以切到逐行表格输入名称。原输入已保留。")
    return name, cursor


def parse_explicit_route(text):
    """Return explicit (sequence text, name) rows, or None for legacy input.

    A colon separates the sequence from a name that may contain digits/spaces.
    Semicolons/newlines separate operations. Quoted names use doubled quotes.
    Mixed or incomplete explicit rows are rejected, never reparsed as compact text.
    """
    if re.search(r"(?:^|[;；\r\n])\s*[0-9０-９]+[ \t]*[:：]", text) is None:
        return None
    rows, cursor, size = [], 0, len(text)
    while cursor < size:
        cursor = _skip_route_space(text, cursor)
        if cursor == size:
            break
        prefix = EXPLICIT_ROUTE_PREFIX.match(text, cursor)
        if prefix is None:
            raise ValueError("请在每道工序号后加冒号，例如“10: 车削；20: 热处理”。原输入已保留。")
        seq = re.match(r"[0-9０-９]+", prefix.group()).group()
        name, cursor = _explicit_route_name(text, prefix.end())
        rows.append((seq, name))
        if cursor < size:
            cursor += 1
    return rows


def preprocess_route_string(route_string: str) -> str:
    """预处理工艺路线字符串（移除分隔符、全角转半角）。"""
    if not route_string:
        return ""

    result = str(route_string).strip()
    if not result:
        return ""

    result = re.sub(SEPARATORS, "", result)
    full_to_half = str.maketrans("０１２３４５６７８９", "0123456789")
    return result.translate(full_to_half)


def route_format_errors(normalized: str) -> List[str]:
    errors: List[str] = []
    if re.match(r"^\d", normalized) is None:
        errors.append(MISSING_START_SEQ_ERROR)
    tail_m = re.search(r"(\d+)$", normalized)
    if tail_m:
        errors.append(missing_tail_op_error(tail_m.group(1)))
    return errors


def route_tokens(normalized: str) -> List[Tuple[str, str]]:
    return re.findall(ROUTE_TOKEN_PATTERN, normalized)
