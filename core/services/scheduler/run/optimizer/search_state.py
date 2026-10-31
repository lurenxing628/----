from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class OptimizerSearchState:
    best: Optional[Dict[str, Any]] = None
