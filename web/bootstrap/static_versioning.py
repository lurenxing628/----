from __future__ import annotations

import os
from typing import Any, Callable, Dict, Set

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


def _parse_versioned_endpoints(app: Flask) -> Set[str]:
    endpoints: Set[str] = {"static", "ui_v2_static.static"}
    raw = app.config.get("STATIC_VERSIONED_ENDPOINTS")
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            name = str(item or "").strip()
            if name:
                endpoints.add(name)
    return endpoints


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
    versioned_endpoints = _parse_versioned_endpoints(app)
    mtime_cache: Dict[str, int] = {}
    version_cache: Dict[str, str] = {}

    def _resolve_static_root(endpoint: str) -> str:
        if endpoint == "static":
            return static_dir
        if endpoint.endswith(".static"):
            bp_name = endpoint.rsplit(".", 1)[0]
            bp = app.blueprints.get(bp_name)
            static_root = getattr(bp, "static_folder", None) if bp is not None else None
            if static_root:
                return str(static_root)
        return static_dir

    def _mtime_version(endpoint: str, filename: Any) -> str:
        rel = _normalize_filename(filename)
        if not rel:
            return ""
        root = _resolve_static_root(endpoint)
        file_path = os.path.join(root, rel.replace("/", os.sep))
        cache_key = f"{endpoint}|{rel}"
        try:
            mtime = int(os.path.getmtime(file_path))
        except Exception:
            return ""
        if mtime_cache.get(cache_key) == mtime:
            return version_cache.get(cache_key, "")
        ver = str(mtime)
        mtime_cache[cache_key] = mtime
        version_cache[cache_key] = ver
        return ver

    def _versioned_url_for(endpoint: str, **values: Any) -> str:
        try:
            if endpoint in versioned_endpoints and "v" not in values:
                version = fixed_version or _mtime_version(endpoint, values.get("filename"))
                if version:
                    values = dict(values)
                    values["v"] = version
        except Exception:
            # 失败时降级到原生 url_for，避免影响页面可用性
            pass
        return flask_url_for(endpoint, **values)

    return _versioned_url_for


def install_versioned_url_for(app: Flask, static_dir: str) -> None:
    versioned_url_for = build_versioned_url_for(app, static_dir)
    app.extensions[EXT_KEY_TEMPLATE_URL_FOR] = versioned_url_for

    @app.context_processor
    def _inject_url_for() -> Dict[str, Callable[..., str]]:
        return {"url_for": versioned_url_for}

    try:
        app.jinja_env.globals["url_for"] = versioned_url_for
    except Exception:
        pass
