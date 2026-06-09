"""单元测试：long_gate 运行时探针 memo（_RUNTIME_FINGERPRINT_CACHE / _runtime_probe_cache_key）。

守护键的语义：同 (探针名, exe realpath, 完整 env 签名) 命中返回同值且不重跑子进程；env 任意差异
或 realpath 变化即换键真跑；仅成功值入缓存（returncode!=0 / strict-raise 一律不缓存）；strict 与
已缓存成功值交互正确（复用、不重跑、不抛）。本组用例正是 overlay 集成守卫（test_long_gate_cache.py:265）
覆盖不到的「仅 env 变化换键」敏感性——防止未来削弱键的 env 维度导致带 env_overlay 的门禁条目
错误复用探针结果而假绿。文件级 autouse 清缓存，隔离各用例。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools import long_gate_fingerprint as fp


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    fp._RUNTIME_FINGERPRINT_CACHE.clear()
    yield
    fp._RUNTIME_FINGERPRINT_CACHE.clear()


class _RunCounter:
    """计数版 subprocess.run 替身，返回固定 CompletedProcess 形态。"""

    def __init__(self, returncode: int = 0, stdout: str = "git version 2.50.0") -> None:
        self.calls = 0
        self._rc = returncode
        self._out = stdout

    def __call__(self, cmd, *args, **kwargs):
        self.calls += 1
        return SimpleNamespace(returncode=self._rc, stdout=self._out, stderr="")


def _patch(monkeypatch, runner, which_result):
    monkeypatch.setattr(fp.subprocess, "run", runner)
    if callable(which_result):
        monkeypatch.setattr(fp.shutil, "which", lambda exe, path=None: which_result(path))
    else:
        monkeypatch.setattr(fp.shutil, "which", lambda exe, path=None: which_result)


def test_same_realpath_and_env_hits_cache_without_rerun(monkeypatch):
    runner = _RunCounter()
    _patch(monkeypatch, runner, "/usr/bin/git")
    env = {"PATH": "/usr/bin", "FOO": "1"}

    v1 = fp._git_version(environment=env)
    v2 = fp._git_version(environment=dict(env))  # 内容相同、对象不同

    assert v1 == v2 == "git version 2.50.0"
    assert runner.calls == 1  # 第二次命中缓存，未重跑


def test_env_only_change_rekeys_and_reruns(monkeypatch):
    runner = _RunCounter()
    _patch(monkeypatch, runner, "/usr/bin/git")  # realpath 不变

    fp._git_version(environment={"PATH": "/usr/bin"})
    fp._git_version(environment={"PATH": "/usr/bin", "NODE_OPTIONS": "--x"})  # 仅 env 变

    assert runner.calls == 2  # env 不同→换键→真跑（守护键的 env 敏感性）


def test_realpath_change_rekeys_and_reruns(monkeypatch):
    runner = _RunCounter()
    seq = iter(["/opt/a/git", "/opt/b/git"])
    _patch(monkeypatch, runner, lambda _path: next(seq))

    fp._git_version(environment={"PATH": "/x"})
    fp._git_version(environment={"PATH": "/x"})  # env 同，但解析出不同 exe

    assert runner.calls == 2


def test_strict_reuses_cached_success_without_rerun_or_raise(monkeypatch):
    runner = _RunCounter()
    _patch(monkeypatch, runner, "/usr/bin/git")
    env = {"PATH": "/usr/bin"}

    v_nonstrict = fp._git_version(strict=False, environment=env)
    v_strict = fp._git_version(strict=True, environment=dict(env))  # 同键

    assert v_nonstrict == v_strict == "git version 2.50.0"
    assert runner.calls == 1  # strict 命中缓存的成功值，不重跑也不抛


def test_nonstrict_failure_not_cached_and_reruns(monkeypatch):
    runner = _RunCounter(returncode=1, stdout="")
    _patch(monkeypatch, runner, "/usr/bin/git")
    env = {"PATH": "/usr/bin"}

    r1 = fp._git_version(strict=False, environment=env)
    r2 = fp._git_version(strict=False, environment=dict(env))

    assert r1 == r2 == "__git_version_unavailable__"
    assert runner.calls == 2  # 失败值不入缓存→每次真跑
    assert fp._RUNTIME_FINGERPRINT_CACHE == {}


def test_strict_failure_raises_and_not_cached(monkeypatch):
    runner = _RunCounter(returncode=1, stdout="")
    _patch(monkeypatch, runner, "/usr/bin/git")

    with pytest.raises(fp.LongGateFingerprintError):
        fp._git_version(strict=True, environment={"PATH": "/usr/bin"})

    assert fp._RUNTIME_FINGERPRINT_CACHE == {}


def test_node_capability_only_caches_passed_value(monkeypatch):
    runner = _RunCounter(returncode=0, stdout="fetch/WebSocket available")
    _patch(monkeypatch, runner, "/usr/bin/node")
    env = {"PATH": "/usr/bin"}

    v1 = fp._node_browser_runtime_capability(environment=env)
    v2 = fp._node_browser_runtime_capability(environment=dict(env))

    assert v1 == v2 and v1.startswith("passed:")
    assert runner.calls == 1  # 成功 capability 命中缓存
