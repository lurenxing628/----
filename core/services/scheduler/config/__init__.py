from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config_page_outcome import ConfigPageSaveOutcome
    from .config_service import ConfigService

_EXPORTS = {
    "ConfigPageSaveOutcome": ".config_page_outcome",
    "ConfigService": ".config_service",
}

__all__ = ["ConfigPageSaveOutcome", "ConfigService"]


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
