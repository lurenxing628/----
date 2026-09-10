"""B02 合同：陈旧 runtime 锁清理的读后删 TOCTOU 守卫。

并发双启动交错场景：崩溃遗留 pid 已死的陈旧锁，进程 A 先判陈旧→删→重建新锁；
进程 B 稍后才执行自己的删除。守卫要求 B 删除前重读比对 payload：
- 内容已被 A 的新锁替换（pid/started_at 必然不同）→ B 必须放弃删除；
- B 回到循环按最新内容重新判定 → A 的新锁活跃 → B 以 RuntimeLockError 拒启；
- 绝不允许 B 把 A 刚重建的新锁当陈旧锁删掉造成双实例同库上线。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import web.bootstrap.launcher_runtime_lock as lock_mod

_STALE_PID = 111
_NEW_PID = 222
_OWNER = "LOCALBOX\\alice"
_EXE = "/tmp/aps.exe"


def _write_lock(lock_path: Path, pid: int, *, started_at: str) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        f"pid={pid}\nowner={_OWNER}\nexe_path={_EXE}\nstarted_at={started_at}\n",
        encoding="utf-8",
    )


def _patch_pid_probes(monkeypatch) -> None:
    states = {_STALE_PID: False, _NEW_PID: True}
    monkeypatch.setattr(lock_mod, "_pid_state", lambda pid: states.get(int(pid), False))
    monkeypatch.setattr(lock_mod, "_pid_matches_contract", lambda pid, expected_exe_path: True)


def test_guard_refuses_delete_when_lock_content_replaced_after_stale_judgement(tmp_path: Path, monkeypatch) -> None:
    _patch_pid_probes(monkeypatch)
    state_dir = tmp_path / "logs"
    lock_path = state_dir / "aps_runtime.lock"

    _write_lock(lock_path, _STALE_PID, started_at="2026-07-19T00:00:00Z")
    stale_result = lock_mod.read_runtime_lock_result_from_path(str(lock_path))
    assert stale_result.ok
    expected_stale = stale_result.payload or {}

    # 判定与删除之间：A 已删旧锁并重建了自己的新锁
    _write_lock(lock_path, _NEW_PID, started_at="2026-07-19T00:00:01Z")

    removed = lock_mod._remove_stale_runtime_lock(str(lock_path), expected_stale)

    assert removed is False, "锁内容已被并发替换时必须放弃删除"
    assert lock_path.exists(), "A 重建的新锁绝不能被 B 删掉"
    assert f"pid={_NEW_PID}" in lock_path.read_text(encoding="utf-8")


def test_guard_still_deletes_when_content_unchanged(tmp_path: Path, monkeypatch) -> None:
    _patch_pid_probes(monkeypatch)
    state_dir = tmp_path / "logs"
    lock_path = state_dir / "aps_runtime.lock"
    _write_lock(lock_path, _STALE_PID, started_at="2026-07-19T00:00:00Z")
    stale_result = lock_mod.read_runtime_lock_result_from_path(str(lock_path))
    assert stale_result.ok

    removed = lock_mod._remove_stale_runtime_lock(str(lock_path), stale_result.payload or {})

    assert removed is True
    assert not lock_path.exists()


def test_interleaved_rebuild_makes_second_starter_refuse_and_keeps_new_lock(tmp_path: Path, monkeypatch) -> None:
    """端到端交错合同：B 走 acquire 循环，判陈旧后 A 完成重建，B 必须放弃删除并最终拒启。"""
    _patch_pid_probes(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "logs"
    lock_path = state_dir / "aps_runtime.lock"
    _write_lock(lock_path, _STALE_PID, started_at="2026-07-19T00:00:00Z")

    calls = {"guard": 0}
    real_guard = lock_mod._remove_stale_runtime_lock

    def _interleaved_guard(path: str, expected_stale):
        # 模拟 A 在 B『判定陈旧』与『执行删除』之间完成了删旧+重建新锁
        calls["guard"] += 1
        _write_lock(Path(path), _NEW_PID, started_at="2026-07-19T00:00:01Z")
        return real_guard(path, expected_stale)

    monkeypatch.setattr(lock_mod, "_remove_stale_runtime_lock", _interleaved_guard)

    with pytest.raises(lock_mod.RuntimeLockError):
        lock_mod.acquire_runtime_lock(
            str(runtime_dir),
            str(state_dir),
            owner=_OWNER,
            exe_path=_EXE,
        )

    assert calls["guard"] == 1, "放弃删除后第二轮按活锁拒启，不应再次尝试删除"
    assert lock_path.exists(), "A 重建的新锁必须原样保留"
    assert f"pid={_NEW_PID}" in lock_path.read_text(encoding="utf-8")


def test_genuine_stale_lock_still_heals_and_acquire_succeeds(tmp_path: Path, monkeypatch) -> None:
    """回归：真正的陈旧锁（无并发交错）仍能被自愈接管。"""
    _patch_pid_probes(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    state_dir = tmp_path / "logs"
    lock_path = state_dir / "aps_runtime.lock"
    _write_lock(lock_path, _STALE_PID, started_at="2026-07-19T00:00:00Z")

    import os

    payload = lock_mod.acquire_runtime_lock(
        str(runtime_dir),
        str(state_dir),
        owner=_OWNER,
        exe_path=_EXE,
    )

    assert int(payload["pid"]) == os.getpid()
    assert f"pid={os.getpid()}" in lock_path.read_text(encoding="utf-8")
    lock_mod.release_runtime_lock(str(state_dir))
    assert not lock_path.exists()
