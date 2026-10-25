from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import OperatorStatus


@dataclass
class Operator:
    operator_id: str
    name: str
    status: str = OperatorStatus.ACTIVE.value  # active/inactive
    remark: Optional[str] = None
    team_id: Optional[str] = None

