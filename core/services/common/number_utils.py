from __future__ import annotations

from typing import Any, Literal, Optional, overload

from core.services.common.strict_parse import (
    parse_optional_float,
    parse_optional_int,
    parse_required_float,
    parse_required_int,
)


@overload
def parse_finite_float(value: Any, *, field: str, allow_none: Literal[False] = False) -> float:
    ...


@overload
def parse_finite_float(value: Any, *, field: str, allow_none: Literal[True]) -> Optional[float]:
    ...


def parse_finite_float(value: Any, *, field: str, allow_none: bool = False) -> Optional[float]:
    """严格浮点解析门面：仅保留 allow_none 兼容形态。"""
    if allow_none:
        return parse_optional_float(value, field=field)
    return parse_required_float(value, field=field)


@overload
def parse_finite_int(value: Any, *, field: str, allow_none: Literal[False] = False) -> int:
    ...


@overload
def parse_finite_int(value: Any, *, field: str, allow_none: Literal[True]) -> Optional[int]:
    ...


def parse_finite_int(value: Any, *, field: str, allow_none: bool = False) -> Optional[int]:
    """严格整数解析门面：仅保留 allow_none 兼容形态。"""
    if allow_none:
        return parse_optional_int(value, field=field)
    return parse_required_int(value, field=field)
