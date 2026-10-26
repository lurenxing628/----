from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .value_domains import INTERNAL


@dataclass
class OpForScheduleAlgo:
    """算法输入工序：排产输入构建一次生成规范值，算法与优化器直接读字段。"""

    id: int
    op_code: str
    batch_id: str
    piece_id: Optional[str]
    seq: int
    op_type_id: str
    op_type_name: str
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

    # 物料到齐当天 0 点；排产输入构建时由规范日期解析一次（workbench/run/input.py）。
    material_ready_date: Optional[datetime] = None


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
    seed_source: Optional[str] = None
    state_revision: Optional[str] = None
    op_type_id: Optional[str] = None


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
    failure_details: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("success 必须是布尔值。")
        for field_name in ("total_ops", "scheduled_ops", "failed_ops"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} 必须是非负整数。")
            if value < 0:
                raise ValueError(f"{field_name} 必须是非负整数。")
