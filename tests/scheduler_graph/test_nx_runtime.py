"""回归测试：scheduler.graph 包惰性加载 networkx 的契约——导入 graph 包本身绝不连带导入 networkx；nx_runtime.import_networkx() 成功返回模块，缺依赖时抛 NetworkXUnavailable（缺少可选依赖），版本不在兼容范围时抛 NetworkXUnavailable（版本不兼容）。"""

from __future__ import annotations

import builtins
import importlib
import sys
import types

import pytest


def test_graph_package_import_does_not_import_networkx(monkeypatch) -> None:
    sys.modules.pop("core.services.scheduler.graph", None)
    sys.modules.pop("networkx", None)

    real_import = builtins.__import__
    imported = []

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "networkx" or name.startswith("networkx."):
            imported.append(name)
            raise AssertionError("graph package import must not import networkx")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    importlib.import_module("core.services.scheduler.graph")

    assert imported == []


def test_import_networkx_success(monkeypatch) -> None:
    from core.services.scheduler.graph import nx_runtime

    fake_nx = types.SimpleNamespace(__version__="3.1")
    monkeypatch.setattr(nx_runtime.importlib, "import_module", lambda name: fake_nx if name == "networkx" else None)

    assert nx_runtime.import_networkx() is fake_nx


def test_import_networkx_rejects_missing_dependency(monkeypatch) -> None:
    from core.services.scheduler.graph import nx_runtime

    def missing(_name):
        raise ImportError("missing")

    monkeypatch.setattr(nx_runtime.importlib, "import_module", missing)

    with pytest.raises(nx_runtime.NetworkXUnavailable, match="缺少可选依赖"):
        nx_runtime.import_networkx()


def test_import_networkx_rejects_wrong_version(monkeypatch) -> None:
    from core.services.scheduler.graph import nx_runtime

    fake_nx = types.SimpleNamespace(__version__="3.2")
    monkeypatch.setattr(nx_runtime.importlib, "import_module", lambda name: fake_nx)

    with pytest.raises(nx_runtime.NetworkXUnavailable, match="版本不兼容"):
        nx_runtime.import_networkx()
