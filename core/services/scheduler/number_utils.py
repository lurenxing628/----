from __future__ import annotations

from typing import Any

from core.services.common.enum_normalizers import normalize_yes_no_wide
from core.services.common.number_utils import parse_finite_float, parse_finite_int


def to_yes_no(value: Any, *, default: str = "no") -> str:
    """
    归一化 yes/no 开关值，返回严格的 "yes" 或 "no"。

    - 会先对输入做 str().strip().lower()
    - 视为真值：yes/y/true/1/on
    - value 为 None 时使用 default（默认 "no"）
    """
    return normalize_yes_no_wide(value, default=default, unknown_policy="no")
