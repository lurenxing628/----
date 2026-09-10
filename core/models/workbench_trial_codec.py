"""Lossless SQLite snapshot encoding, including legacy BLOB and REAL values."""

import base64
import json
import math
from typing import Optional

from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_trial import MAX_TRIAL_BYTES, reject


def packed(value):
    if isinstance(value, bytes):
        return {"$sqlite_blob": base64.b64encode(value).decode("ascii")}
    if type(value) is float and not math.isfinite(value):
        return {"$sqlite_real": value.hex()}
    if type(value) is dict:
        return {key: packed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [packed(item) for item in value]
    return value


def unpacked(value):
    if type(value) is dict:
        if set(value) == {"$sqlite_blob"}:
            return base64.b64decode(value["$sqlite_blob"], validate=True)
        if set(value) == {"$sqlite_real"}:
            return float.fromhex(value["$sqlite_real"])
        return {key: unpacked(item) for key, item in value.items()}
    if type(value) is list:
        return [unpacked(item) for item in value]
    return value


def dump(value):
    text = canonical_json(packed(value))
    if len(text.encode("utf-8")) > MAX_TRIAL_BYTES:
        reject("query_too_large", "完整试调快照超过64 MiB上限，未截断原范围。", 413)
    return text


def load(text: object, fingerprint: Optional[str] = None):
    if type(text) is not str or len(text.encode("utf-8")) > MAX_TRIAL_BYTES:
        reject("trial_snapshot_invalid", "持久试调快照缺失或超过上限。")
    try:
        value = json.loads(text)
        if fingerprint is not None and input_fingerprint(value) != fingerprint:
            reject("trial_snapshot_invalid", "持久试调快照校验失败，未重建最新计划。")
        return unpacked(value)
    except (ValueError, TypeError) as exc:
        from core.models.workbench_command import WorkbenchCommandRejected
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        reject("trial_snapshot_invalid", "持久试调快照无法读取，未重建最新计划。")


def load_object(text: object, fingerprint: Optional[str] = None):
    return require_object(load(text, fingerprint))


def require_object(value: object):
    if type(value) is not dict:
        reject("trial_snapshot_invalid", "持久试调快照必须为对象，未推测或替换原数据。")
    return value


def fingerprint(value):
    return input_fingerprint(packed(value))
