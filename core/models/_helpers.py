from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional, Union

from core.shared.strict_parse import integer_value, is_blank_input

RowLike = Union[sqlite3.Row, Dict[str, Any]]


def parse_int(value: Any, *, field: str) -> int:
    """
    读 NOT NULL 整数列：值必须是整数（int、整数值浮点、整数值数字文本或 UTF-8 字节，见 integer_value）。
    空值、bool、非整数值、NaN/Inf、脏文本都是存储损坏，抛 ValueError，不拿默认值顶替。
    """
    number = integer_value(value)
    if number is None:
        raise ValueError(f"{field} 必须是整数，当前值无法读取：{value!r}")
    return number


def parse_optional_int(value: Any, *, field: str) -> Optional[int]:
    """读可空整数列：None 或全空白串读作 None，其余值同 parse_int，坏值抛 ValueError。"""
    if is_blank_input(value):
        return None
    return parse_int(value, field=field)

