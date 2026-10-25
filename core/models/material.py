from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import MaterialStatus


@dataclass
class Material:
    material_id: str
    name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    stock_qty: float = 0.0
    status: str = MaterialStatus.ACTIVE.value  # active/inactive
    remark: Optional[str] = None

