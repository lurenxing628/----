"""回归测试：运行日志读取层边界契约——时间戳锚点切分/倒序/200 条上限、跨 64KB 块边界的
多字节中文完整不出 �、>256KB 超长条目头尾保留+截断标记且切点回退合法 UTF-8 边界、
真实坏字节 replace 显示不抛、无锚点文件单条 UNKNOWN 兜底（读取量同受上限）、
头行无 [LEVEL] 时 level=UNKNOWN、文件不存在返回空。"""

from __future__ import annotations

import pytest

from core.services.system.runtime_log_reader import (
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    NO_ANCHOR_HEAD,
    TAIL_BLOCK_SIZE,
    TRUNCATION_MARKER,
    read_log_entries_tail,
)


def _entry_bytes(ts: str, level: str, message: str) -> bytes:
    return f"{ts} [{level}] web [routes.py:10]: {message}\n".encode()


def _write(tmp_path, data: bytes):
    path = tmp_path / "sample.log"
    path.write_bytes(data)
    return str(path)


def test_entries_are_newest_first_with_head_body_level(tmp_path):
    data = (
        _entry_bytes("2026-06-11 10:00:00", "INFO", "第一条")
        + "2026-06-11 10:00:01 [ERROR] web [r.py:1]:\n  报错了\nTraceback (most recent call last):\n  boom\n".encode()
        + _entry_bytes("2026-06-11 10:00:02", "WARNING", "第三条")
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert [e["level"] for e in entries] == ["WARNING", "ERROR", "INFO"]
    assert entries[0]["head"].endswith("第三条")
    assert "Traceback" in entries[1]["body"]


def test_max_entries_cap(tmp_path):
    data = b"".join(
        _entry_bytes(f"2026-06-11 10:{i // 60:02d}:{i % 60:02d}", "INFO", f"条目{i}")
        for i in range(MAX_ENTRIES + 50)
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == MAX_ENTRIES
    assert entries[0]["head"].endswith(f"条目{MAX_ENTRIES + 49}")


def test_multibyte_char_across_block_boundary_intact(tmp_path):
    # 构造一条消息恰好让“界”字的 3 字节横跨 64KB 块边界：
    # 文件尾部第一块读 TAIL_BLOCK_SIZE 字节，让该字符的字节落在切点两侧。
    head = b"2026-06-11 10:00:01 [INFO] web [r.py:1]: "
    marker = "块边界字符界".encode()
    first = _entry_bytes("2026-06-11 10:00:00", "INFO", "前导")
    # 让第二条的总长度使 marker 跨在 file_size - TAIL_BLOCK_SIZE 处
    target_cut = len(first) + len(head) + len(marker) - 2  # 切在“界”3 字节中间
    pad = target_cut + TAIL_BLOCK_SIZE - (len(first) + len(head) + len(marker))
    data = first + head + marker + b"x" * pad + b"\n"
    assert len(data) > TAIL_BLOCK_SIZE
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == 2
    assert "界" in entries[0]["head"]
    assert "�" not in entries[0]["head"]
    assert "�" not in entries[0]["body"]


def test_oversize_entry_truncated_head_tail_no_fake_replacement_char(tmp_path):
    # 超长条目：纯中文填充让任何按字节一刀切都可能切出半字符，断言无假 �
    filler = ("中" * 1000 + "\n") * (MAX_ENTRY_BYTES // 3000 + 50)
    data = (
        _entry_bytes("2026-06-11 10:00:00", "INFO", "前一条")
        + ("2026-06-11 10:00:01 [ERROR] web [r.py:1]: 超长开始\n" + filler + "超长结束\n").encode("utf-8")
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == 2
    top = entries[0]
    assert top["level"] == "ERROR"
    assert TRUNCATION_MARKER in top["body"]
    assert "超长开始" in top["head"]
    assert "超长结束" in top["body"]
    assert "�" not in top["head"] and "�" not in top["body"]


def test_scan_continues_past_oversize_entry(tmp_path):
    # 超长条目巡锚成功后，更早的正常条目仍能继续切出（含文件头第一条）
    filler = b"z" * (MAX_ENTRY_BYTES + TAIL_BLOCK_SIZE)
    data = (
        _entry_bytes("2026-06-11 09:00:00", "INFO", "最早一条")
        + _entry_bytes("2026-06-11 09:30:00", "WARNING", "第二条")
        + b"2026-06-11 10:00:00 [ERROR] web [r.py:1]: oversize\n" + filler + b"\n"
        + _entry_bytes("2026-06-11 11:00:00", "INFO", "最新一条")
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert [e["level"] for e in entries] == ["INFO", "ERROR", "WARNING", "INFO"]
    assert entries[0]["head"].endswith("最新一条")
    assert TRUNCATION_MARKER in entries[1]["body"]
    assert "oversize" in entries[1]["head"]
    assert entries[3]["head"].endswith("最早一条")


def test_oversize_entry_hunt_budget_exhausted_falls_back_unanchored(tmp_path):
    # 锚点距文件尾超过巡锚 IO 预算：放弃头半，按无锚点兜底呈现尾半（不读完超大文件）
    from core.services.system.runtime_log_reader import ENTRY_HUNT_BUDGET_BYTES

    data = (
        _entry_bytes("2026-06-11 10:00:00", "INFO", "遥远的开头")
        + b"y" * (ENTRY_HUNT_BUDGET_BYTES + TAIL_BLOCK_SIZE * 2)
        + "尾部内容\n".encode()
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == 1
    assert entries[0]["level"] == "UNKNOWN"
    assert "尾部内容" in entries[0]["body"]


def test_real_bad_bytes_render_replacement_not_raise(tmp_path):
    data = (
        b"2026-06-11 10:00:00 [INFO] web [r.py:1]: ok\n"
        + b"2026-06-11 10:00:01 [ERROR] web [r.py:1]: bad\xff\xfe bytes\n"
    )
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert entries[0]["level"] == "ERROR"
    assert "�" in entries[0]["head"]


def test_unanchored_file_single_unknown_entry(tmp_path):
    entries = read_log_entries_tail(_write(tmp_path, "没有时间戳的纯文本\n第二行\n".encode()))
    assert len(entries) == 1
    assert entries[0]["level"] == "UNKNOWN"
    assert entries[0]["head"] == NO_ANCHOR_HEAD
    assert "第二行" in entries[0]["body"]


def test_unanchored_huge_file_capped_not_full_read(tmp_path):
    # 无锚点大文件：回扫受 MAX_ENTRY_BYTES 限制，只呈现尾部内容
    data = b"x" * (MAX_ENTRY_BYTES * 3) + "尾部标记".encode()
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == 1
    assert entries[0]["level"] == "UNKNOWN"
    assert "尾部标记" in entries[0]["body"]
    assert len(entries[0]["body"].encode("utf-8")) <= MAX_ENTRY_BYTES


def test_head_without_level_token_is_unknown(tmp_path):
    # launcher 行格式变体：时间戳后无 [LEVEL]（锚点要求 [ 开头，故构造 [ 后小写）
    data = b"2026-06-11 10:00:00 [boot] launcher text\n"
    entries = read_log_entries_tail(_write(tmp_path, data))
    assert len(entries) == 1
    assert entries[0]["level"] == "UNKNOWN"


def test_missing_file_returns_empty(tmp_path):
    assert read_log_entries_tail(str(tmp_path / "absent.log")) == []


def test_empty_file_returns_empty(tmp_path):
    assert read_log_entries_tail(_write(tmp_path, b"")) == []


def test_io_error_propagates(tmp_path):
    path = _write(tmp_path, b"2026-06-11 10:00:00 [INFO] x\n")
    import core.services.system.runtime_log_reader as mod

    real_open = open

    def boom(*args, **kwargs):
        raise OSError("disk error")

    # 仅替换模块内 open；不吞错契约：OSError 必须穿透给路由层
    mod.__dict__["open"] = boom
    try:
        with pytest.raises(OSError):
            read_log_entries_tail(path)
    finally:
        mod.__dict__.pop("open", None)
    assert open is real_open
