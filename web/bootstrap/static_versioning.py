from __future__ import annotations

import os
from typing import Any, Callable, Dict, Tuple

from flask import Flask
from flask import url_for as flask_url_for

EXT_KEY_TEMPLATE_URL_FOR = "aps.template_url_for"


def _normalize_filename(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\\", "/")
    while text.startswith("/"):
        text = text[1:]
    return text


def _warn_once(app: Flask, code: str, message: str) -> None:
    seen_key = "aps.static_versioning.warnings"
    seen = app.extensions.setdefault(seen_key, set())
    if code in seen:
        return
    seen.add(code)
    app.logger.warning(message)


def _pick_fixed_version(app: Flask) -> str:
    env_v = str(os.environ.get("APS_STATIC_VERSION") or "").strip()
    if env_v:
        return env_v
    cfg_v = str(app.config.get("STATIC_ASSET_VERSION") or "").strip()
    if cfg_v:
        return cfg_v
    return ""


def build_versioned_url_for(app: Flask, static_dir: str) -> Callable[..., str]:
    fixed_version = _pick_fixed_version(app)
    # 版本缓存：一个 key 一次性写入 (mtime, version) 元组。threaded=True 下所有请求
    # 线程无锁共享本缓存；拆成两个 dict「先写 mtime 再写 version」存在 check-then-act
    # 竞态窗口（读侧命中新 mtime 却读到空/旧 version，audit 2026-07-19 D05）。
    # 单 dict 单次赋值在 GIL 下原子：读侧要么命中完整旧对，要么命中完整新对。
    version_cache: Dict[str, Tuple[int, str]] = {}

    def _mtime_version(filename: Any) -> str:
        rel = _normalize_filename(filename)
        if not rel:
            return ""
        file_path = os.path.join(static_dir, rel.replace("/", os.sep))
        cache_key = f"static|{rel}"
        try:
            mtime = int(os.path.getmtime(file_path))
        except OSError as exc:
            _warn_once(app, f"mtime:{cache_key}", f"静态资源版本号读取失败，已使用原始 URL：{rel}（{exc}）")
            return ""
        cached = version_cache.get(cache_key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        ver = str(mtime)
        version_cache[cache_key] = (mtime, ver)
        return ver

    def _versioned_url_for(endpoint: str, **values: Any) -> str:
        if endpoint == "static" and "v" not in values:
            version = fixed_version or _mtime_version(values.get("filename"))
            if version:
                values["v"] = version
        return flask_url_for(endpoint, **values)

    return _versioned_url_for


def install_versioned_url_for(app: Flask, static_dir: str) -> None:
    versioned_url_for = build_versioned_url_for(app, static_dir)
    app.extensions[EXT_KEY_TEMPLATE_URL_FOR] = versioned_url_for

    @app.context_processor
    def _inject_url_for() -> Dict[str, Callable[..., str]]:
        return {"url_for": versioned_url_for}

    app.jinja_env.globals["url_for"] = versioned_url_for
