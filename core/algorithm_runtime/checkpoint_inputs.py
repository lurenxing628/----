"""Value-only checkpoint input evidence; unsupported objects never become repr-based keys."""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from types import SimpleNamespace
from typing import Any

from core.errors import ValidationError


def input_value(value: Any, *, field: str, depth: int = 0) -> Any:
    """Canonical native values, preserving ordered containers and rejecting dynamic objects."""
    kind = type(value)
    if kind in (type(None), bool, int, str):
        return kind.__name__, value
    if kind is float and math.isfinite(value):
        return "float", value.hex()
    if kind in (date, datetime, time):
        if kind in (datetime, time) and value.tzinfo is not None:
            unsupported_input(field)
        return kind.__name__, value.isoformat()
    if depth > 12 or kind not in (dict, list, tuple, set, frozenset):
        unsupported_input(field)
    if kind is dict:
        return "dict", tuple((input_value(key, field=field, depth=depth + 1),
                              input_value(item, field=field, depth=depth + 1)) for key, item in value.items())
    items = tuple(input_value(item, field=field, depth=depth + 1) for item in value)
    return kind.__name__, tuple(sorted(items, key=repr)) if kind in (set, frozenset) else items


def input_record(record: Any, *, field: str) -> Any:
    """Snapshot plain records completely, including batch quantity, dates and priority."""
    kind = type(record)
    is_dc = kind is not SimpleNamespace and is_dataclass(record)
    if kind is not SimpleNamespace and not is_dc:
        unsupported_input(field)
    try:
        names = set(vars(record))
    except TypeError:
        unsupported_input(field)
    if any(type(key) is not str for key in names):
        unsupported_input(field)
    if is_dc:
        names.update(member.name for member in fields(record))
    encoded_dict = "dict", tuple(
        (("str", key), input_value(getattr(record, key), field=field, depth=1))
        for key in sorted(names)
    )
    return kind.__module__, kind.__qualname__, encoded_dict


def unsupported_input(field: str) -> None:
    raise ValidationError("解码断点无法证明输入内容稳定，请使用全量解码。", field="decode_checkpoint",
                          details={"reason": "decode_checkpoint_unsupported_input", "input_field": field})
