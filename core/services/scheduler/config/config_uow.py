from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigWriteUnitOfWork:
    repo: Any
    tx_manager: Any
    logger: Any = None
    op_logger: Any = None


__all__ = ["ConfigWriteUnitOfWork"]
