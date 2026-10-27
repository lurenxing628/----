from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import SupplierStatus


@dataclass
class Supplier:
    supplier_id: str
    name: str
    default_days: float = 1.0
    status: str = SupplierStatus.ACTIVE.value  # active/inactive
    remark: Optional[str] = None

