from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import YesNo


@dataclass
class Part:
    part_no: str
    part_name: str
    route_raw: Optional[str] = None
    route_parsed: str = YesNo.NO.value  # yes/no
    remark: Optional[str] = None

