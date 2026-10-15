"""Lossless canonical SQLite content for comparisons and saved documents."""

import base64
import json
import math
from datetime import date, datetime


def packed(value, *, json_input=False):
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
    if type(value) is dict:
        keys = set(value)
        if keys in ({"$sqlite_blob"}, {"$sqlite_real"}, {"$sqlite_dict"}, {"storage_type", "iso"}):
            return {"$sqlite_dict": {key: packed(item, json_input=json_input) for key, item in value.items()}}
        return {key: packed(item, json_input=json_input) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [packed(item, json_input=json_input) for item in value]
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
