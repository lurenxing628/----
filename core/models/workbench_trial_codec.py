"""Lossless SQLite snapshot encoding, including legacy BLOB and REAL values."""

import json

from core.models.content import packed as packed
from core.models.content import same as same
from core.models.content import unpacked
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


def _load_document(text):
    size = len(text.encode("utf-8")) if type(text) is str else 0
    if type(text) is not str or size > MAX_TRIAL_BYTES:
        reject("trial_snapshot_invalid", "试调数据读不到或超过上限。请刷新后重试。")
    try:
        return unpacked(json.loads(text)), size
    except (ValueError, TypeError):
        reject("trial_snapshot_invalid", "试调数据读不出来，这里不改用最新计划。请刷新后重试。")


def load_object_with_size(text):
    """Decode one stored fragment and retain its actual UTF-8 byte count."""
    value, size = _load_document(text)
    return require_object(value), size


def load(text: object):
    return _load_document(text)[0]


def load_object(text: object):
    return require_object(load(text))


def require_object(value: object):
    if type(value) is not dict:
        reject("trial_snapshot_invalid", "试调数据格式不对，这里不替换原数据。请刷新后重试。")
    return value
