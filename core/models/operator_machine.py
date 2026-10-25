from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperatorMachine:
    operator_id: str
    machine_id: str
    skill_level: str  # 正式写入口径：beginner/normal/expert；skilled 仅历史兼容别名
    is_primary: str  # yes/no（预留）

