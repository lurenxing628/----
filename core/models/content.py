"""Lossless canonical SQLite content for comparisons and saved documents."""

import base64
import json
import math
from datetime import date, datetime

_JSON_SCALARS = frozenset((str, int, bool, type(None)))
_RESERVED_KEYS = frozenset((frozenset(("$sqlite_blob",)), frozenset(("$sqlite_real",)),
                            frozenset(("$sqlite_dict",)), frozenset(("storage_type", "iso"))))


def packed(value, *, json_input=False):
    kind = type(value)
    if kind is dict:
        result = value
        for key, item in value.items():
            converted = item if type(item) in _JSON_SCALARS else packed(item, json_input=json_input)
            if converted is not item:
                if result is value:
                    result = dict(value)
                result[key] = converted
        if len(value) in (1, 2) and frozenset(value) in _RESERVED_KEYS:
            return {"$sqlite_dict": result}
        return result
    if kind in (list, tuple):
        result = value
        for index, item in enumerate(value):
            converted = item if type(item) in _JSON_SCALARS else packed(item, json_input=json_input)
            if converted is not item:
                if result is value:
                    result = list(value)
                result[index] = converted
        return result
    if isinstance(value, (date, datetime)):
        if json_input:
            raise TypeError("JSON input does not support date values")
        return {"storage_type": type(value).__name__, "iso": value.isoformat()}
    if isinstance(value, bytes):
        if json_input:
            raise TypeError("JSON input does not support binary values")
        return {"$sqlite_blob": base64.b64encode(value).decode("ascii")}
    if type(value) is float and not math.isfinite(value):
        if json_input:
            raise ValueError("JSON input does not support non-finite numbers")
        return {"$sqlite_real": value.hex()}
    return value


def unpacked(value):
    if type(value) is dict:
        if set(value) == {"$sqlite_dict"}:
            if type(value["$sqlite_dict"]) is not dict:
                raise ValueError("Escaped SQLite document is not a dictionary")
            return {key: unpacked(item) for key, item in value["$sqlite_dict"].items()}
        if set(value) == {"storage_type", "iso"} and value["storage_type"] in ("date", "datetime"):
            cls = datetime if value["storage_type"] == "datetime" else date
            return cls.fromisoformat(value["iso"])
        if set(value) == {"$sqlite_blob"}:
            return base64.b64decode(value["$sqlite_blob"], validate=True)
        if set(value) == {"$sqlite_real"}:
            return float.fromhex(value["$sqlite_real"])
        return {key: unpacked(item) for key, item in value.items()}
    if type(value) is list:
        return [unpacked(item) for item in value]
    return value


def content_text(value, *, json_input=False):
    return json.dumps(packed(value, json_input=json_input), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def same(left, right):
    """Compare values without merging boolean, integer and REAL representations."""
    return content_text(left) == content_text(right)
