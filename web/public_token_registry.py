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

import secrets
import threading
import time
from typing import Any, Dict

from flask import current_app

from core.infrastructure.errors import ValidationError

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
    """scope 内部结构：tokens(token→entry) + by_value(value→最新 token 的反向索引)。

    by_value 只指向该 value 最新签发的 token；改签后旧 token 仍留在 tokens 里按原
    expires_at 存活。所有删除必须走 _drop_token 以保持两个映射同步。
    """
    registry = _registry()
    state = registry.get(scope)
    if state is None:
        state = {"tokens": {}, "by_value": {}}
        registry[scope] = state
    return state


def _drop_token(state: Dict[str, Any], token: str) -> None:
    entry = state["tokens"].pop(token, None)
    if entry is None:
        return
    value = entry.get("value")
    if state["by_value"].get(value) == token:
        state["by_value"].pop(value, None)


def _cleanup_scope(state: Dict[str, Any], now: float) -> None:
    tokens = state["tokens"]
    expired = [token for token, entry in tokens.items() if float(entry.get("expires_at") or 0) <= now]
    for token in expired:
        _drop_token(state, token)
    overflow = len(tokens) - _MAX_SCOPE_TOKENS
    if overflow <= 0:
        return
    # 上限淘汰是最后防线:过期项已在上面清掉,剩余按“最久未使用”淘汰
    # (last_used_at,兜底 created_at),避免把旧页面仍在活跃使用的入口挤出。
    ordered = sorted(
        tokens.items(),
        key=lambda item: float(item[1].get("last_used_at") or item[1].get("created_at") or 0),
    )
    for token, _entry in ordered[:overflow]:
        _drop_token(state, token)


def issue_public_token(scope: str, value: Any, *, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> str:
    value_text = _text(value)
    if not value_text:
        return ""
    scope_text = _text(scope)
    if not scope_text:
        raise ValueError("公开 token scope 不能为空。")
    now = time.time()
    effective_ttl = max(60, int(ttl_seconds))
    with _LOCK:
        state = _scope_state(scope_text)
        _cleanup_scope(state, now)
        tokens = state["tokens"]
        by_value = state["by_value"]
        existing_token = by_value.get(value_text)
        if existing_token:
            entry = tokens.get(existing_token)
            if entry is not None and float(entry.get("expires_at") or 0) - now >= effective_ttl * _REUSE_MIN_REMAINING_RATIO:
                # 幂等复用:不延长 expires_at(TTL 语义保持“过期即拒”),
                # 只刷新使用时间供上限淘汰的 LRU 排序参考。
                entry["last_used_at"] = now
                return existing_token
            # 剩余寿命不足复用门槛:改签新 token,by_value 指向新 token;
            # 旧 token 保留至其原 expires_at,旧页面入口不因改签提前失效。
        for _attempt in range(16):
            token = secrets.token_urlsafe(_TOKEN_BYTES)
            if token not in tokens:
                tokens[token] = {
                    "value": value_text,
                    "created_at": now,
                    "last_used_at": now,
                    "expires_at": now + effective_ttl,
                }
                by_value[value_text] = token
                return token
    raise RuntimeError("无法生成唯一公开 token。")


def resolve_public_token(scope: str, token: Any, *, message: str, field: str) -> str:
    token_text = _text(token)
    if not token_text:
        raise ValidationError(message, field=field)
    now = time.time()
    with _LOCK:
        state = _scope_state(_text(scope))
        entry = state["tokens"].get(token_text)
        if not entry:
            raise ValidationError(message, field=field)
        if float(entry.get("expires_at") or 0) <= now:
            _drop_token(state, token_text)
            raise ValidationError(message, field=field)
        value = _text(entry.get("value"))
        if not value:
            _drop_token(state, token_text)
            raise ValidationError(message, field=field)
        entry["last_used_at"] = now
        return value


__all__ = ["issue_public_token", "resolve_public_token"]
