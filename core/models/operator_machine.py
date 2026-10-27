from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperatorMachine:
    operator_id: str
    machine_id: str
    skill_level: str  # beginner/normal/expert
    is_primary: str  # yes/no（预留）

