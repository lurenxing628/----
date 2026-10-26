"""Lossless SQLite snapshot encoding, including legacy BLOB and REAL values."""

from typing import NoReturn

from core.models.content import content_text, unpacked
from core.models.workbench_trial import MAX_TRIAL_BYTES, reject
from core.shared.strict_json import load_strict_json


def encode_trial_text(value):
    text = content_text(value)
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_TRIAL_BYTES:
        reject("query_too_large", "这次试调的数据超过 64 MB 上限，没有读取。请缩小批次范围。", 413)
    return text, encoded


def dump(value):
    return encode_trial_text(value)[0]


def dump_document(value):
    """Save the original document; the legacy digest column remains empty."""
    text, _ = encode_trial_text(value)
    return text, None


def _unreadable() -> NoReturn:
    reject("trial_snapshot_invalid", "试调数据读不出来，这里不改用最新计划。请刷新后重试。")


def _load_document(text):
    size = len(text.encode("utf-8")) if type(text) is str else 0
    if type(text) is not str or size > MAX_TRIAL_BYTES:
        reject("trial_snapshot_invalid", "试调数据读不到或超过上限。请刷新后重试。")
    # 严格读取的拒绝是 WorkbenchCommandRejected（ValueError 子类），放在下面只管 unpacked 的 try 外面。
    document = load_strict_json(text, on_malformed=_unreadable)
    try:
        return unpacked(document), size
    except (ValueError, TypeError):
        _unreadable()


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
