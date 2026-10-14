"""Lossless SQLite snapshot encoding, including legacy BLOB and REAL values."""

import json
from typing import Optional

from core.models.content import packed as packed
from core.models.content import same as same
from core.models.content import unpacked as unpacked
from core.models.workbench_command import canonical_json
from core.models.workbench_trial import MAX_TRIAL_BYTES, reject


def _encoded(value):
    text = canonical_json(packed(value))
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_TRIAL_BYTES:
        reject("query_too_large", "这次试调的数据超过 64 MB 上限，没有读取。请缩小批次范围。", 413)
    return text, encoded


def dump(value):
    return _encoded(value)[0]


def dump_document(value):
    """Save the original document; the legacy digest column remains empty."""
    text, _ = _encoded(value)
    return text, None


def load_document(text: object, fingerprint: Optional[str] = None):
    """Parse the original packed document and typed values; retain legacy metadata."""
    if type(text) is not str or len(text.encode("utf-8")) > MAX_TRIAL_BYTES:
        reject("trial_snapshot_invalid", "试调数据读不到或超过上限。请刷新后重试。")
    try:
        value = json.loads(text)
        return value, unpacked(value)
    except (ValueError, TypeError) as exc:
        from core.models.workbench_command import WorkbenchCommandRejected
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        reject("trial_snapshot_invalid", "试调数据读不出来，这里不改用最新计划。请刷新后重试。")


def load(text: object, fingerprint: Optional[str] = None):
    return load_document(text, fingerprint)[1]


def load_object(text: object, fingerprint: Optional[str] = None):
    return require_object(load(text, fingerprint))


def require_object(value: object):
    if type(value) is not dict:
        reject("trial_snapshot_invalid", "试调数据格式不对，这里不替换原数据。请刷新后重试。")
    return value
