from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import OpTypeCategory


@dataclass
class OpType:
    op_type_id: str
    name: str
    category: str = OpTypeCategory.INTERNAL.value  # internal/external/both
    default_hours: Optional[float] = None
    remark: Optional[str] = None

