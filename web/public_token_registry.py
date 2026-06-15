"""服务端不透明公开 token 登记表。

把 plan_context_token / 工序保存 token 等“页面上下文”从可被 base64 解码的签名 payload
换成服务端随机 token，URL 上只暴露不可逆随机串。

【重要部署约束】登记表存放在 current_app.extensions（进程内存），并由模块级 _LOCK 保证
线程安全（生产 make_server(threaded=True) 为单进程多线程）。一旦改为多进程部署
（gunicorn/uwsgi 多 worker、多实例），A worker 颁发的 token 在 B worker 必然 miss，
触发“入口已失效，请刷新页面”。届时必须改为共享存储（Redis/DB）或自带签名校验的 token，
不能沿用本进程内实现。
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
# 进程级可重入锁：保护 registry 的读改写序列（issue/resolve/cleanup），消除 threaded=True 下
# “先列出过期项再逐个 pop”的 cleanup 竞态。RLock 容忍同线程嵌套调用，不会自锁。
_LOCK = threading.RLock()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _registry() -> Dict[str, Dict[str, Dict[str, Any]]]:
    registry = current_app.extensions.get(_EXTENSION_KEY)
    if registry is None:
        registry = {}
        current_app.extensions[_EXTENSION_KEY] = registry
    return registry


def _scope_store(scope: str) -> Dict[str, Dict[str, Any]]:
    registry = _registry()
    return registry.setdefault(scope, {})


def _cleanup_scope(store: Dict[str, Dict[str, Any]], now: float) -> None:
    expired = [token for token, entry in store.items() if float(entry.get("expires_at") or 0) <= now]
    for token in expired:
        store.pop(token, None)
    if len(store) <= _MAX_SCOPE_TOKENS:
        return
    ordered = sorted(store.items(), key=lambda item: float(item[1].get("created_at") or 0))
    overflow = len(store) - _MAX_SCOPE_TOKENS
    for token, _entry in ordered[:overflow]:
        store.pop(token, None)


def issue_public_token(scope: str, value: Any, *, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> str:
    value_text = _text(value)
    if not value_text:
        return ""
    scope_text = _text(scope)
    if not scope_text:
        raise ValueError("公开 token scope 不能为空。")
    now = time.time()
    with _LOCK:
        store = _scope_store(scope_text)
        _cleanup_scope(store, now)
        for _attempt in range(16):
            token = secrets.token_urlsafe(_TOKEN_BYTES)
            if token not in store:
                store[token] = {
                    "value": value_text,
                    "created_at": now,
                    "expires_at": now + max(60, int(ttl_seconds)),
                }
                return token
    raise RuntimeError("无法生成唯一公开 token。")


def resolve_public_token(scope: str, token: Any, *, message: str, field: str) -> str:
    token_text = _text(token)
    if not token_text:
        raise ValidationError(message, field=field)
    now = time.time()
    with _LOCK:
        store = _scope_store(_text(scope))
        entry = store.get(token_text)
        if not entry:
            raise ValidationError(message, field=field)
        if float(entry.get("expires_at") or 0) <= now:
            store.pop(token_text, None)
            raise ValidationError(message, field=field)
        value = _text(entry.get("value"))
        if not value:
            store.pop(token_text, None)
            raise ValidationError(message, field=field)
        return value


__all__ = ["issue_public_token", "resolve_public_token"]
