from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.services.scheduler.graph import nx_runtime


def test_import_networkx_uses_lazy_import_and_accepts_expected_version(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_nx = SimpleNamespace(__version__="3.1")
    calls = []

    def _fake_import_module(name: str):
        calls.append(name)
        return fake_nx

    monkeypatch.setattr(nx_runtime.importlib, "import_module", _fake_import_module)

    assert nx_runtime.import_networkx() is fake_nx
    assert calls == ["networkx"]


def test_import_networkx_missing_dependency_raises_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_import_module(name: str):
        raise ImportError("missing")

    monkeypatch.setattr(nx_runtime.importlib, "import_module", _fake_import_module)

    with pytest.raises(nx_runtime.NetworkXUnavailable) as exc_info:
        nx_runtime.import_networkx()

    assert "networkx==3.1" in str(exc_info.value)
    assert "requirements-optimizer-lite-win7.txt" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ImportError)


def test_import_networkx_load_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_import_module(name: str):
        raise RuntimeError("broken package")

    monkeypatch.setattr(nx_runtime.importlib, "import_module", _fake_import_module)

    with pytest.raises(nx_runtime.NetworkXUnavailable) as exc_info:
        nx_runtime.import_networkx()

    assert "加载可选依赖" in str(exc_info.value)
    assert "networkx==3.1" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_import_networkx_rejects_wrong_version(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_nx = SimpleNamespace(__version__="3.2")

    monkeypatch.setattr(nx_runtime.importlib, "import_module", lambda name: fake_nx)

    with pytest.raises(nx_runtime.NetworkXUnavailable) as exc_info:
        nx_runtime.import_networkx()

    assert "当前 3.2" in str(exc_info.value)
    assert "期望 3.1" in str(exc_info.value)


def test_import_networkx_rejects_missing_version(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_nx = SimpleNamespace()

    monkeypatch.setattr(nx_runtime.importlib, "import_module", lambda name: fake_nx)

    with pytest.raises(nx_runtime.NetworkXUnavailable) as exc_info:
        nx_runtime.import_networkx()

    assert "unknown" in str(exc_info.value)
    assert "期望 3.1" in str(exc_info.value)


def test_requirement_helpers_are_stable() -> None:
    assert nx_runtime.expected_networkx_version() == "3.1"
    assert nx_runtime.optional_networkx_requirement() == "networkx==3.1"
