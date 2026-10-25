from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BatchOperation:
    """批次工序行；唯一生产构造边界 run_input_rows.operation_model 已校验全部字段。"""

    id: int
    op_code: str
    batch_id: str
    piece_id: Optional[str]
    seq: int
    op_type_id: str
    op_type_name: str
    source: str  # internal/external
    machine_id: Optional[str]
    operator_id: Optional[str]
    supplier_id: Optional[str]
    setup_hours: float
    unit_hours: float
    ext_days: Optional[float]
    status: str  # pending/scheduled/processing/completed/skipped
    created_at: Optional[str]
