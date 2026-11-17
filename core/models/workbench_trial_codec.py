"""Lossless SQLite snapshot encoding, including legacy BLOB and REAL values."""

from typing import NoReturn

from core.models.content import StoredJsonCorrupt, content_text, read_stored_json, unpacked
from core.models.workbench_trial import MAX_TRIAL_BYTES, reject


def encode_trial_text(value):
    text = content_text(value)
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_TRIAL_BYTES:
        reject("query_too_large", f"这次试调的数据超过 {MAX_TRIAL_BYTES // (1024 * 1024)} MB 上限，没有读取。请缩小批次范围。", 413)
    return text, encoded


def dump(value):
    return encode_trial_text(value)[0]


def _unreadable() -> NoReturn:
    reject("trial_snapshot_invalid", "试调数据读不出来，这里不改用最新计划。请刷新后重试。")


def load_object_with_size(text):
    """Decode one stored document (every writer dumps a dict) and retain its actual UTF-8 byte count."""
    # 先量字节再解码，超限的不解码；量之前要是文本，不是文本就是存储损坏，与解码失败同一种错误。
    if type(text) is not str:
        raise StoredJsonCorrupt()
    size = len(text.encode("utf-8"))
    if size > MAX_TRIAL_BYTES:
        reject("trial_snapshot_invalid", "试调数据超过读取上限。请刷新后重试。")
    # 解码失败的 StoredJsonCorrupt 也是 ValueError 子类，放在下面只管 unpacked 的 try 外面。
    document = read_stored_json(text, dict)
    try:
        value = unpacked(document)
    except (ValueError, TypeError):
        _unreadable()
    # read_stored_json 只证明 JSON 顶层是对象；顶层恰为保留转义形状（storage_type/iso、$sqlite_blob）的对象
    # 会被 unpacked 还原成日期、时间或字节串。写入方只写字典，还原后不是字典就是存储损坏。
    if type(value) is not dict:
        reject("trial_snapshot_invalid", "试调数据格式不对，这里不替换原数据。请刷新后重试。")
    return value, size


def load_object(text: object):
    return load_object_with_size(text)[0]
