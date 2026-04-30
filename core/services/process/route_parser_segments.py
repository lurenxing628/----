from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.models.enums import SourceType


@dataclass
class ExternalGroup:
    """外部工序组（连续 external）。"""

    group_id: str
    start_seq: int
    end_seq: int
    operations: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "start_seq": self.start_seq,
            "end_seq": self.end_seq,
            "operations": [x.to_dict() for x in self.operations],
        }


def identify_external_groups(operations: List[Any], part_no: str) -> List[ExternalGroup]:
    """识别连续外部工序组，并给外部工序填充 ext_group_id。"""
    groups: List[ExternalGroup] = []
    current_group: Optional[ExternalGroup] = None
    group_counter = 1

    for op in operations:
        if op.source == SourceType.EXTERNAL.value:
            if current_group is None:
                group_id = f"{part_no}_EXT_{group_counter}"
                current_group = ExternalGroup(
                    group_id=group_id,
                    start_seq=op.seq,
                    end_seq=op.seq,
                    operations=[op],
                )
                op.ext_group_id = group_id
            else:
                current_group.end_seq = op.seq
                current_group.operations.append(op)
                op.ext_group_id = current_group.group_id
        else:
            if current_group is not None:
                groups.append(current_group)
                current_group = None
                group_counter += 1

    if current_group is not None:
        groups.append(current_group)

    return groups
