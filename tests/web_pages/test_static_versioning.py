"""回归测试：静态资源版本号注入(static_versioning)——build_versioned_url_for 对缺失静态文件回退原始 /static 路径并只记一次
"静态资源版本号读取失败"告警；install_versioned_url_for 在 jinja globals 注入失败时不崩溃、仍登记扩展并告警；
但 filename.__str__ 等非预期异常不被吞掉，应原样抛出；版本缓存必须单 dict 原子写入
(mtime, version) 元组，不许拆两个 dict 先后写（audit 2026-07-19 D05 竞态）。"""

from __future__ import annotations

import os
import types

import pytest
from flask import Flask


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []

    def warning(self, message: str) -> None:
        self.warnings.append(str(message))


def test_versioned_url_for_logs_missing_static_file_once(tmp_path) -> None:
    from web.bootstrap.static_versioning import build_versioned_url_for

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        assert versioned_url_for("static", filename="missing.css") == "/static/missing.css"
        assert versioned_url_for("static", filename="missing.css") == "/static/missing.css"

    assert len(app.logger.warnings) == 1
    assert "静态资源版本号读取失败" in app.logger.warnings[0]


def test_install_versioned_url_for_logs_jinja_injection_failure(tmp_path) -> None:
    from web.bootstrap.static_versioning import EXT_KEY_TEMPLATE_URL_FOR, install_versioned_url_for

    class _BrokenGlobals(dict):
        def __setitem__(self, key, value):
            raise RuntimeError("globals locked")

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    app.jinja_env.globals = _BrokenGlobals()

    install_versioned_url_for(app, str(tmp_path))

    assert EXT_KEY_TEMPLATE_URL_FOR in app.extensions
    assert any("模板静态资源版本函数注入失败" in item for item in app.logger.warnings)


def test_versioned_url_for_does_not_hide_unexpected_filename_errors(tmp_path) -> None:
    from web.bootstrap.static_versioning import build_versioned_url_for

    class _BrokenFilename:
        def __str__(self) -> str:
            raise RuntimeError("filename exploded")

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        with pytest.raises(RuntimeError, match="filename exploded"):
            versioned_url_for("static", filename=_BrokenFilename())


def test_versioned_url_for_fills_and_refreshes_version_on_mtime_change(tmp_path) -> None:
    from web.bootstrap.static_versioning import build_versioned_url_for

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    asset = tmp_path / "app.js"
    asset.write_text("v1", encoding="utf-8")
    os.utime(str(asset), (1000, 1000))
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        assert versioned_url_for("static", filename="app.js") == "/static/app.js?v=1000"
        # 缓存命中：同 mtime 复用版本号
        assert versioned_url_for("static", filename="app.js") == "/static/app.js?v=1000"
        os.utime(str(asset), (2000, 2000))
        # 热更新：mtime 变化后立即返回新版本号，不发旧值
        assert versioned_url_for("static", filename="app.js") == "/static/app.js?v=2000"


def _closure_dicts(fn) -> list:
    """收集函数闭包图里可达的所有 dict（版本缓存必然在内）。"""
    seen = set()
    stack = [fn]
    found = []
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        for cell in getattr(obj, "__closure__", None) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, dict):
                found.append(value)
            elif isinstance(value, types.FunctionType):
                stack.append(value)
    return found


def test_version_cache_pairs_mtime_and_version_in_single_atomic_write(tmp_path) -> None:
    """竞态合同（audit 2026-07-19 D05）：mtime 与 version 必须存进同一个 dict 的
    同一个值（单次赋值在 GIL 下原子）。拆成两个 dict「先写 mtime 后写 version」在
    threaded=True 下有 check-then-act 窗口：并发读侧命中新 mtime 却拿到空/旧版本号。
    本测试确定性锁写序结构：闭包里只允许存在一个缓存 dict，且每个条目都是
    (mtime, version) 成对元组。"""
    from web.bootstrap.static_versioning import build_versioned_url_for

    app = Flask(__name__)
    app.logger = _CollectingLogger()  # type: ignore[assignment]
    asset = tmp_path / "app.css"
    asset.write_text("body{}", encoding="utf-8")
    os.utime(str(asset), (1234, 1234))
    versioned_url_for = build_versioned_url_for(app, str(tmp_path))

    with app.test_request_context():
        versioned_url_for("static", filename="app.css")
        os.utime(str(asset), (5678, 5678))
        versioned_url_for("static", filename="app.css")

    caches = [d for d in _closure_dicts(versioned_url_for) if d]
    assert len(caches) == 1, "版本缓存必须是单一 dict（两个 dict 的写序竞态正是 D05 根因）"
    cache = caches[0]
    for key, value in cache.items():
        assert isinstance(value, tuple) and len(value) == 2, (
            f"缓存值必须是 (mtime, version) 成对元组：{key}={value!r}"
        )
        mtime, version = value
        assert version == str(mtime), f"version 必须与同一元组内的 mtime 一致：{key}={value!r}"
    assert cache["static|app.css"][0] == 5678, "热更新后缓存应持有新 mtime 的完整新对"
