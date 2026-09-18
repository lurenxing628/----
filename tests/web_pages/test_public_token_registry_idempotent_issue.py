"""B09 合同：公开 token 幂等签发 + 上限淘汰最后防线（先清过期，再按最久未使用）。

背景（2026-07-19 盲区扫描 B09）：op-update token 每次渲染逐工序无去重签发，
长命登记表靠 5000 上限按 created_at 淘汰，重度浏览会把早先页面仍在使用的
保存入口挤出，用户提交时表单被丢弃。本文件锁住修复后的三条合同：

1. 同 (scope, value) 有效期内重复签发返回同一 token，登记表不膨胀；
2. TTL 语义不放宽：复用不延长 expires_at，过期即拒、过期后重签新 token；
3. 上限淘汰先清已过期项，再按最久未使用（LRU）淘汰，不牺牲活跃入口。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

import web.public_token_registry as registry
from core.infrastructure.errors import ValidationError

_MSG = "入口已失效，请刷新页面后重试。"


@pytest.fixture
def app() -> Flask:
    return Flask(__name__)


def _clock(monkeypatch, start: float = 1_000_000.0):
    """把 registry 模块内的 time 换成可控时钟（模块局部替换，monkeypatch 自动还原）。"""
    state = {"now": start}
    monkeypatch.setattr(registry, "time", SimpleNamespace(time=lambda: state["now"]))
    return state


def _resolve(scope: str, token: str) -> str:
    return registry.resolve_public_token(scope, token, message=_MSG, field="f")


def _scope_tokens(app: Flask, scope: str):
    return app.extensions[registry._EXTENSION_KEY][scope]["tokens"]


# ---------------------------------------------------------------------------
# 合同 1：幂等签发，同 (scope, value) 复用不重签，登记表不膨胀
# ---------------------------------------------------------------------------


def test_same_scope_value_reuses_token_and_store_does_not_grow(app, monkeypatch):
    _clock(monkeypatch)
    with app.app_context():
        first = registry.issue_public_token("scope-a", "op-1")
        for _ in range(50):
            assert registry.issue_public_token("scope-a", "op-1") == first
        # 反复渲染同一页面不再堆积新 token——这是 B09 膨胀根因的正向钉死
        assert len(_scope_tokens(app, "scope-a")) == 1
        assert _resolve("scope-a", first) == "op-1"


def test_distinct_values_and_scopes_get_distinct_tokens(app, monkeypatch):
    _clock(monkeypatch)
    with app.app_context():
        t1 = registry.issue_public_token("scope-a", "op-1")
        t2 = registry.issue_public_token("scope-a", "op-2")
        t3 = registry.issue_public_token("scope-b", "op-1")
        assert len({t1, t2, t3}) == 3
        assert _resolve("scope-a", t1) == "op-1"
        assert _resolve("scope-a", t2) == "op-2"
        assert _resolve("scope-b", t3) == "op-1"


# ---------------------------------------------------------------------------
# 合同 2：TTL 语义保持——复用不延长寿命，过期即拒，过期后重签
# ---------------------------------------------------------------------------


def test_reuse_does_not_extend_expiry(app, monkeypatch):
    clock = _clock(monkeypatch)
    with app.app_context():
        first = registry.issue_public_token("s", "v", ttl_seconds=3600)
        clock["now"] += 1000
        # 剩余 2600s >= 1800s(半 TTL)，复用同一 token
        assert registry.issue_public_token("s", "v", ttl_seconds=3600) == first
        # 越过“原始”过期点：复用不得把寿命续到 1000+3600
        clock["now"] += 2601
        with pytest.raises(ValidationError):
            _resolve("s", first)


def test_expired_token_rejected_then_fresh_token_issued(app, monkeypatch):
    clock = _clock(monkeypatch)
    with app.app_context():
        first = registry.issue_public_token("s", "v", ttl_seconds=3600)
        clock["now"] += 3601
        with pytest.raises(ValidationError):
            _resolve("s", first)
        second = registry.issue_public_token("s", "v", ttl_seconds=3600)
        assert second != first
        assert _resolve("s", second) == "v"


def test_near_expiry_issues_fresh_token_and_old_one_lives_out_its_ttl(app, monkeypatch):
    clock = _clock(monkeypatch)
    with app.app_context():
        first = registry.issue_public_token("s", "v", ttl_seconds=3600)
        clock["now"] += 2000
        # 剩余 1600s < 1800s(半 TTL)：改签新 token，保证新页面入口至少还有半个 TTL
        second = registry.issue_public_token("s", "v", ttl_seconds=3600)
        assert second != first
        # 旧 token 不因改签提前失效，仍活到自己的 expires_at
        assert _resolve("s", first) == "v"
        assert _resolve("s", second) == "v"
        clock["now"] += 1601  # t=3601：first 过期，second（t=2000 签发）仍有效
        with pytest.raises(ValidationError):
            _resolve("s", first)
        assert _resolve("s", second) == "v"


# ---------------------------------------------------------------------------
# 合同 3：上限淘汰最后防线——先清过期项，再按最久未使用淘汰
# ---------------------------------------------------------------------------


def test_overflow_cleanup_prefers_expired_entries(app, monkeypatch):
    clock = _clock(monkeypatch)
    monkeypatch.setattr(registry, "_MAX_SCOPE_TOKENS", 2)
    with app.app_context():
        tok_a = registry.issue_public_token("s", "va", ttl_seconds=3600)
        tok_b = registry.issue_public_token("s", "vb", ttl_seconds=3600)
        clock["now"] += 10
        tok_short = registry.issue_public_token("s", "vc", ttl_seconds=60)  # t=70 过期
        clock["now"] += 70  # t=80：tok_short 已过期，店内 3 条超上限 2
        tok_d = registry.issue_public_token("s", "vd", ttl_seconds=3600)
        # 过期项先被清掉，未过期的 va/vb 虽更老、更久未用也不被牺牲
        with pytest.raises(ValidationError):
            _resolve("s", tok_short)
        assert _resolve("s", tok_a) == "va"
        assert _resolve("s", tok_b) == "vb"
        assert _resolve("s", tok_d) == "vd"


def test_overflow_evicts_least_recently_used_not_oldest_created(app, monkeypatch):
    clock = _clock(monkeypatch)
    monkeypatch.setattr(registry, "_MAX_SCOPE_TOKENS", 2)
    with app.app_context():
        tok_a = registry.issue_public_token("s", "va", ttl_seconds=3600)  # 最老签发
        tok_b = registry.issue_public_token("s", "vb", ttl_seconds=3600)
        clock["now"] += 10
        _resolve("s", tok_a)  # va 刚被使用（B09 场景里“旧页面仍在保存”的入口）
        clock["now"] += 10
        tok_c = registry.issue_public_token("s", "vc", ttl_seconds=3600)  # 无过期项，暂容 3 条
        clock["now"] += 10
        tok_d = registry.issue_public_token("s", "vd", ttl_seconds=3600)  # 触发淘汰 1 条
        # 按 LRU 淘汰 vb（从未使用），而不是按 created_at 淘汰最老但活跃的 va
        with pytest.raises(ValidationError):
            _resolve("s", tok_b)
        assert _resolve("s", tok_a) == "va"
        assert _resolve("s", tok_c) == "vc"
        assert _resolve("s", tok_d) == "vd"


# ---------------------------------------------------------------------------
# 既有边界行为不回归
# ---------------------------------------------------------------------------


def test_empty_value_returns_empty_and_unknown_token_rejected(app, monkeypatch):
    _clock(monkeypatch)
    with app.app_context():
        assert registry.issue_public_token("s", "") == ""
        assert registry.issue_public_token("s", None) == ""
        with pytest.raises(ValidationError):
            _resolve("s", "no-such-token")
        with pytest.raises(ValidationError):
            _resolve("s", "")


def test_empty_scope_still_raises(app, monkeypatch):
    _clock(monkeypatch)
    with app.app_context():
        with pytest.raises(ValueError):
            registry.issue_public_token("", "v")
