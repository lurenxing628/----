"""服务端不透明公开 token 登记表。

把 plan_context_token / 工序保存 token 等“页面上下文”从可被 base64 解码的签名 payload
换成服务端随机 token，URL 上只暴露不可逆随机串。

【重要部署约束】登记表存放在 current_app.extensions（进程内存），并由模块级 _LOCK 保证
线程安全（生产 make_server(threaded=True) 为单进程多线程）。一旦改为多进程部署
（gunicorn/uwsgi 多 worker、多实例），A worker 颁发的 token 在 B worker 必然 miss，
触发“入口已失效，请刷新页面”。届时必须改为共享存储（Redis/DB）或自带签名校验的 token，
不能沿用本进程内实现。

【幂等签发,2026-07-19 盲区扫描 B09】同 (scope, value) 在有效期内重复签发直接复用
已有 token,不重签、不延长 expires_at,从根上消除“同页面反复渲染/多标签页浏览”导致的
登记表膨胀,避免早先页面仍在使用的 token 被 5000 上限挤出而丢弃用户已填表单。
仅当已有 token 剩余寿命不足本次请求 TTL 的一半时才改签新 token,保证新渲染页面的保存
入口至少还有半个 TTL 可用;旧 token 仍按原 expires_at 存活,到期即拒,TTL 语义不放宽。
上限淘汰保留为最后防线:先清已过期项,再按“最久未使用”淘汰,不牺牲仍在活跃使用的入口。
"""

from __future__ import annotations

import heapq
import secrets
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from flask import current_app

from core.errors import ValidationError

_EXTENSION_KEY = "aps_public_opaque_tokens"
_DEFAULT_TTL_SECONDS = 12 * 60 * 60
_MAX_SCOPE_TOKENS = 5000
_TOKEN_BYTES = 24
# 幂等复用门槛:已有 token 剩余寿命 >= 请求 TTL × 该比例时复用;不足则改签新 token,
# 避免新打开的页面拿到一个即将过期的旧入口(旧 token 不受影响,仍活到原 expires_at)。
_REUSE_MIN_REMAINING_RATIO = 0.5
# 进程级可重入锁：保护 registry 的读改写序列（issue/resolve/cleanup），消除 threaded=True 下
# “先列出过期项再逐个 pop”的 cleanup 竞态。RLock 容忍同线程嵌套调用，不会自锁。
_LOCK = threading.RLock()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _registry() -> Dict[str, Dict[str, Any]]:
    registry = current_app.extensions.get(_EXTENSION_KEY)
    if registry is None:
        registry = {}
        current_app.extensions[_EXTENSION_KEY] = registry
    return registry


def _scope_state(scope: str) -> Dict[str, Any]:
    """Scope owns tokens and a grouped reverse index: shared facts → small key → token.

    Each key points to its latest token. Superseded tokens keep their original
    expiry. _drop_token removes an empty index group together with its last key.
    next_expiry amortizes cleanup without changing expiry checks on resolve.
    """
    registry = _registry()
    state = registry.get(scope)
    if state is None:
        state = {"tokens": {}, "by_value": {}, "next_expiry": float("inf")}
        registry[scope] = state
    return state


class _ValueIndex(dict):
    """The existing reverse-index group, including its canonical group key."""

    def __init__(self, group):
        super().__init__()
        self.group = group
        self.attached = True


def _drop_token(state: Dict[str, Any], token: str) -> None:
    entry = state["tokens"].pop(token, None)
    if entry is None:
        return
    index = entry["index"]
    if index.get(entry["index_key"]) == token:
        index.pop(entry["index_key"], None)
        if not index:
            state["by_value"].pop(index.group, None)
            index.attached = False


def _cleanup_scope(state: Dict[str, Any], now: float) -> None:
    tokens = state["tokens"]
    # 摊销清理:还没到最早到期时刻、也没超上限时不可能有可清的项,不逐条扫描整个作用域
    # (每签发一个 token 都全量扫描,一次签发几千个就是平方级)。过期即拒由 resolve 现查,不受影响。
    if len(tokens) <= _MAX_SCOPE_TOKENS and now < state["next_expiry"]:
        return
    expired = [token for token, entry in tokens.items() if entry["expires_at"] <= now]
    for token in expired:
        _drop_token(state, token)
    state["next_expiry"] = min((entry["expires_at"] for entry in tokens.values()), default=float("inf"))
    overflow = len(tokens) - _MAX_SCOPE_TOKENS
    if overflow <= 0:
        return
    # 上限淘汰是最后防线:过期项已在上面清掉,剩余按“最久未使用”淘汰
    ordered = heapq.nsmallest(
        overflow,
        tokens.items(),
        key=lambda item: item[1]["last_used_at"],
    )
    for token, _entry in ordered:
        _drop_token(state, token)


class PublicTokenIssuer:
    """One operation owns one lookup of its shared facts in the original index.

    Each issue still performs the real clock/cleanup under the registry lock.
    An index removed by expiry or LRU is detached by _drop_token; a later issue
    then joins the current group again instead of retaining an orphan index.
    """

    def __init__(self, scope: str, *, group: Any = None, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        scope_text = _text(scope)
        if not scope_text:
            raise ValueError("公开 token scope 不能为空。")
        with _LOCK:
            self._state = _scope_state(scope_text)
        self._group = group
        self._index: Optional[_ValueIndex] = None
        self._ttl = max(60, int(ttl_seconds))

    def issue_with_expiry(self, value: Any, *, key: Any = None) -> Tuple[str, float]:
        """Retain the value directly; only the per-subject key varies in a batch."""
        if value is None or isinstance(value, str) and not value.strip():
            raise ValueError("公开 token 的内容不能为空。")
        return self.issue_bound_with_expiry(lambda _group: value, key=value if key is None else key)

    def issue_bound_with_expiry(self, binding: Callable[[Any], Any], *, key: Any) -> Tuple[str, float]:
        """Build the retained binding from the group's canonical facts under the lock."""
        with _LOCK:
            now = time.time()
            state = self._state
            _cleanup_scope(state, now)
            index = self._index
            new_index = False
            if index is None or not index.attached:
                index = state["by_value"].get(self._group)
                if index is None:
                    index = _ValueIndex(self._group)
                    new_index = True
            if not new_index:
                self._index = index
                self._group = index.group
            tokens = state["tokens"]
            existing_token = index.get(key)
            if existing_token:
                entry = tokens.get(existing_token)
                if entry is not None and entry["expires_at"] - now >= self._ttl * _REUSE_MIN_REMAINING_RATIO:
                    entry["last_used_at"] = now
                    return existing_token, entry["expires_at"]
            value = binding(index.group)
            if new_index:
                state["by_value"][index.group] = index
                self._index, self._group = index, index.group
            for _attempt in range(16):
                token = secrets.token_urlsafe(_TOKEN_BYTES)
                if token not in tokens:
                    expires = now + self._ttl
                    tokens[token] = {
                        "value": value, "index": index, "index_key": key,
                        "last_used_at": now, "expires_at": expires,
                    }
                    index[key] = token
                    state["next_expiry"] = min(state["next_expiry"], expires)
                    return token, expires
        raise RuntimeError("无法生成唯一公开 token。")


def issue_public_token(scope: str, value: Any, *, ttl_seconds: int = _DEFAULT_TTL_SECONDS,
                       key: Any = None, group: Any = None) -> str:
    return PublicTokenIssuer(scope, group=group, ttl_seconds=ttl_seconds).issue_with_expiry(value, key=key)[0]


def resolve_public_token(scope: str, token: Any, *, message: str, field: str) -> Any:
    token_text = _text(token)
    if not token_text:
        raise ValidationError(message, field=field)
    with _LOCK:
        now = time.time()
        state = _scope_state(_text(scope))
        entry = state["tokens"].get(token_text)
        if not entry:
            raise ValidationError(message, field=field)
        if entry["expires_at"] <= now:
            _drop_token(state, token_text)
            raise ValidationError(message, field=field)
        entry["last_used_at"] = now
        return entry["value"]


def issue_public_token_with_expiry(scope: str, value: Any, *, ttl_seconds: int,
                                   key: Any, group: Any = None) -> Tuple[str, float]:
    """Return the actual expiry, including when idempotent issuance reuses a token."""
    return PublicTokenIssuer(scope, group=group, ttl_seconds=ttl_seconds).issue_with_expiry(value, key=key)


__all__ = ["PublicTokenIssuer", "issue_public_token", "resolve_public_token", "issue_public_token_with_expiry"]
