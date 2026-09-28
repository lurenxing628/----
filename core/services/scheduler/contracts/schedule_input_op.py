"""算法输入工序合同：排产输入构建与优化器多起点去重共用的纯数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OpForScheduleAlgo:
    """算法输入工序（补充 merged 外部组信息）。"""

    id: int
    op_code: str
    batch_id: str
    piece_id: Optional[str]
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
    merge_context_degraded: bool = False
    merge_context_events: List[Dict[str, Any]] = field(default_factory=list)

    material_ready_date: Optional[str] = None
