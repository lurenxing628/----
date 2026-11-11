from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BatchOperation:
    """批次工序行模型；进入 build_algo_operations 前由 run_input_rows.operation_model 完成字段校验，已落库行复核可经 stored_algo_inputs.stored_batch_operation 按原值构造。"""

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
