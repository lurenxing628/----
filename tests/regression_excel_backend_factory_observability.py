from __future__ import annotations

import pytest

import core.services.common.excel_backend_factory as factory_mod
from core.services.common.openpyxl_backend import OpenpyxlBackend


class _RegistryStub:
    def __init__(self, provider) -> None:
        self._provider = provider

    def get(self, key, default=None):
        assert key == factory_mod._PANDAS_BACKEND_CAPABILITY
        return self._provider if self._provider is not None else default


def test_get_excel_backend_auto_logs_warning_and_degrades_to_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings = []

    def _broken_provider():
        raise RuntimeError("provider boom")

    def _warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(factory_mod, "get_plugin_registry", lambda: _RegistryStub(_broken_provider))
    monkeypatch.setattr(factory_mod._LOGGER, "warning", _warning)

    backend = factory_mod.get_excel_backend()

    assert isinstance(backend, OpenpyxlBackend)
    assert any("excel_backend.pandas" in message and "provider boom" in message for message in warnings), warnings


def test_get_excel_backend_explicit_pandas_missing_capability_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory_mod, "get_plugin_registry", lambda: _RegistryStub(None))

    with pytest.raises(RuntimeError, match=r"excel_backend\.pandas"):
        factory_mod.get_excel_backend("pandas")


def test_get_excel_backend_invalid_prefer_raises_value_error() -> None:
    with pytest.raises(ValueError, match="prefer"):
        factory_mod.get_excel_backend("invalid")
