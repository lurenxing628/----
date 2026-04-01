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


def _safe_float(value: Any, *, default: Optional[float]) -> Optional[float]:
    """
    安全浮点解析：
    - None / "" / "   " -> default
    - 非数字 -> default（避免 build_algo_operations 因 ValueError 崩溃整次排产）
    """
    if value is None:
        return default
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return default
        try:
            return float(s)
        except Exception:
            return default
    try:
        return float(value)
    except Exception:
        return default


def build_algo_operations(svc, reschedulable_operations: List[Any]) -> List[OpForScheduleAlgo]:
    """
    把已收口的可重排工序（BatchOperation）转换为算法输入。

    约定：
    - `completed/skipped` 之类的终态过滤由 `ScheduleService` 统一负责；
    - 本层只消费调用方传入的 `reschedulable_operations`，不再自行扩散状态语义。
    """
    algo_ops: List[OpForScheduleAlgo] = []
    for op in reschedulable_operations:
        ext_group_id = None
        merge_mode = None
        total_days = None
        if (op.source or "").strip().lower() == SourceType.EXTERNAL.value:
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
                setup_hours=float(_safe_float(getattr(op, "setup_hours", None), default=0.0) or 0.0),
                unit_hours=float(_safe_float(getattr(op, "unit_hours", None), default=0.0) or 0.0),
                ext_days=_safe_float(getattr(op, "ext_days", None), default=None),
                ext_group_id=ext_group_id,
                ext_merge_mode=merge_mode,
                ext_group_total_days=_safe_float(total_days, default=None),
            )
        )
    return algo_ops

