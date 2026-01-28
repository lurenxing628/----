from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from core.models.enums import SourceType


@dataclass
class OpForScheduleAlgo:
    """算法输入工序（补充 merged 外部组信息）。"""

    id: int
    op_code: str
    batch_id: str
    seq: int
    op_type_id: Optional[str]
    op_type_name: Optional[str]
    source: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    supplier_id: Optional[str]
    setup_hours: float
    unit_hours: float
    ext_days: Optional[float]
    # 外部组信息（来自 PartOperations + ExternalGroups）
    ext_group_id: Optional[str]
    ext_merge_mode: Optional[str]
    ext_group_total_days: Optional[float]


def build_algo_operations(svc, operations: List[Any]) -> List[OpForScheduleAlgo]:
    """
    把批次工序（BatchOperation）转换为算法输入（补充 merged 外部组信息）。
    """
    algo_ops: List[OpForScheduleAlgo] = []
    for op in operations:
        ext_group_id = None
        merge_mode = None
        total_days = None
        if (op.source or "").strip() == SourceType.EXTERNAL.value:
            tmpl, grp = svc._get_template_and_group_for_op(op)
            ext_group_id = (tmpl.ext_group_id if tmpl else None) if tmpl else None
            merge_mode = grp.merge_mode if grp else None
            total_days = grp.total_days if grp else None

        algo_ops.append(
            OpForScheduleAlgo(
                id=int(op.id or 0),
                op_code=op.op_code,
                batch_id=op.batch_id,
                seq=int(op.seq or 0),
                op_type_id=getattr(op, "op_type_id", None),
                op_type_name=getattr(op, "op_type_name", None),
                source=op.source,
                machine_id=op.machine_id,
                operator_id=op.operator_id,
                supplier_id=op.supplier_id,
                setup_hours=float(op.setup_hours or 0.0),
                unit_hours=float(op.unit_hours or 0.0),
                ext_days=float(op.ext_days) if op.ext_days is not None and op.ext_days != "" else None,
                ext_group_id=ext_group_id,
                ext_merge_mode=merge_mode,
                ext_group_total_days=float(total_days) if total_days is not None and total_days != "" else None,
            )
        )
    return algo_ops

