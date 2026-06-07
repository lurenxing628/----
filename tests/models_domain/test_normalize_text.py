"""回归测试：normalize_text 把 None/空串/纯空白归一为 None、对非字符串(0/123)与首尾空白做 strip 转字符串；
append_unique_text_messages 容忍 None 缓冲区，接受单值/列表/集合输入，按首次出现顺序去重并丢弃空与 falsy 文本。"""

from __future__ import annotations

from core.services.common.normalize import append_unique_text_messages, normalize_text


def test_normalize_text_none_and_blank() -> None:
    assert normalize_text(None) is None
    assert normalize_text("") is None
    assert normalize_text("   ") is None


def test_normalize_text_str_and_non_str() -> None:
    assert normalize_text(" a ") == "a"
    assert normalize_text("0") == "0"
    assert normalize_text(0) == "0"
    assert normalize_text(123) == "123"


def test_append_unique_text_messages_accepts_none_buffer() -> None:
    append_unique_text_messages(None, ["告警", "", None])


def test_append_unique_text_messages_single_value_and_dedup_order() -> None:
    buffer = ["已有告警"]
    append_unique_text_messages(buffer, " 新告警 ")
    append_unique_text_messages(buffer, ["", None, "已有告警", "第二条", "新告警", 0])
    assert buffer == ["已有告警", "新告警", "第二条"]


def test_append_unique_text_messages_accepts_set_input() -> None:
    buffer = []
    append_unique_text_messages(buffer, {"集合告警"})
    assert buffer == ["集合告警"]
