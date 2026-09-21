"""回归测试：浏览器车道 pre-push 抽样的轮转语义。

抽样要顶用，靠的是"N 次 push 之后整条车道都被跑过一遍"。所以这里锁的是轮转本身：
接着上次往下取、到尾绕回开头、车道增删文件之后还能按文件名重新定位。随机抽样做不到这些，
也不可复现，所以不要改成随机。
"""

from __future__ import annotations

import json

from tools.browser_lane_sample import pick, read_cursor, write_cursor

TARGETS = ["a.py", "b.py", "c.py", "d.py"]


def test_first_run_starts_from_the_beginning() -> None:
    assert pick(TARGETS, 2, "") == ["a.py", "b.py"]


def test_next_run_continues_after_the_last_file() -> None:
    assert pick(TARGETS, 2, "b.py") == ["c.py", "d.py"]


def test_cursor_wraps_around_at_the_end() -> None:
    assert pick(TARGETS, 3, "c.py") == ["d.py", "a.py", "b.py"]


def test_a_full_cycle_covers_every_file() -> None:
    """轮转的全部意义：一圈下来一个都不落。"""
    seen, last = [], ""
    for _ in range(len(TARGETS)):
        batch = pick(TARGETS, 1, last)
        seen.extend(batch)
        last = batch[-1]
    assert sorted(seen) == sorted(TARGETS)


def test_unknown_cursor_falls_back_to_the_beginning() -> None:
    """车道里删掉了游标指着的那个文件，不该整个卡住。"""
    assert pick(TARGETS, 2, "已经删掉的文件.py") == ["a.py", "b.py"]


def test_count_larger_than_the_lane_does_not_repeat_files() -> None:
    assert pick(TARGETS, 99, "") == TARGETS


def test_empty_lane_selects_nothing() -> None:
    assert pick([], 2, "") == []


def test_cursor_round_trips_through_disk(tmp_path, monkeypatch) -> None:
    from tools import browser_lane_sample

    monkeypatch.setattr(browser_lane_sample, "CURSOR_PATH", tmp_path / "nested" / "sample-cursor.json")
    assert read_cursor() == ""
    write_cursor("c.py", outcome="failed")
    assert read_cursor() == "c.py"
    payload = json.loads((tmp_path / "nested" / "sample-cursor.json").read_text(encoding="utf-8"))
    assert payload["outcome"] == "failed"


def test_unreadable_cursor_is_treated_as_never_run(tmp_path, monkeypatch) -> None:
    from tools import browser_lane_sample

    path = tmp_path / "sample-cursor.json"
    path.write_text("不是 JSON", encoding="utf-8")
    monkeypatch.setattr(browser_lane_sample, "CURSOR_PATH", path)
    assert read_cursor() == ""


def test_cursor_stays_out_of_version_control() -> None:
    """游标一旦进了版本控制，pre-push 写它就会弄脏工作区，把要求干净树的门禁卡死。"""
    import subprocess

    from tools.browser_lane_sample import CURSOR_PATH, ROOT

    relative = CURSOR_PATH.relative_to(ROOT)
    result = subprocess.run(["git", "check-ignore", str(relative)], cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, f"{relative} 没有被 .gitignore 忽略"
