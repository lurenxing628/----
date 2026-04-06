from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from core.algorithms.value_domains import INTERNAL


@dataclass
class ScheduleResult:
    """单道工序排程结果（供落库与追溯使用）。"""

    op_id: int  # BatchOperations.id
    op_code: str
    batch_id: str
    seq: int
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: str = INTERNAL  # internal/external
    op_type_name: Optional[str] = None


@dataclass
class ScheduleSummary:
    """排程摘要（供留痕与页面提示使用）。"""

    success: bool
    total_ops: int
    scheduled_ops: int
    failed_ops: int
    warnings: List[str]
    errors: List[str]
    duration_seconds: float

