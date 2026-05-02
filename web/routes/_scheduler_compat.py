from __future__ import annotations

import importlib
from types import ModuleType


def load_scheduler_route_module(domain_module: str) -> ModuleType:
    """Load one scheduler leaf module for legacy import paths."""
    return importlib.import_module(domain_module, __package__)
