from __future__ import annotations

import re
from typing import List, Tuple

from core.services.process.route_parser_errors import MISSING_START_SEQ_ERROR, missing_tail_op_error

# 需要移除的分隔符（空格、逗号、顿号、破折号、箭头等）
# 说明：
# - 文档/用户输入里常见 "->" / "→" / "-" / "—" 等分隔；若不移除 ">" 会污染工种名（如 "钳>"）。
# - 这里用“字符集合”覆盖：'-' 与 '>' 分别移除，即可兼容 "->"。
SEPARATORS = r"[\s,，、\-—–→>＞]+"
ROUTE_TOKEN_PATTERN = r"(\d+)([^\d]+)"


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
