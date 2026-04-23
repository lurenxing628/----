from __future__ import annotations

import importlib
from types import ModuleType


def load_scheduler_route_module(domain_module: str) -> ModuleType:
    """Load the fully-registered scheduler route graph before exposing a leaf module."""
    importlib.import_module(".scheduler", __package__)
    return importlib.import_module(domain_module, __package__)
