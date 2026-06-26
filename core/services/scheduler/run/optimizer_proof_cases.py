from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

DEFAULT_NODE_LIMIT = 50000


@dataclass(frozen=True)
class TinyBatchSpec:
    batch_id: str
    due_date: str
    priority: str = "normal"
    quantity: float = 1.0
    created_at: Optional[str] = None


@dataclass(frozen=True)
class TinyOperationSpec:
    op_id: int
    op_code: str
    batch_id: str
    seq: int
    machine_id: str
    operator_id: str
    duration_hours: float
    op_type_name: str = "standard"


@dataclass(frozen=True)
class TinyBenchmarkCase:
    slug: str
    objective_name: str
    batches: Tuple[TinyBatchSpec, ...]
    operations: Tuple[TinyOperationSpec, ...]
    dispatch_mode: str = "sgs"
    dispatch_rule: str = "slack"
    start_dt: datetime = datetime(2026, 1, 1, 8, 0, 0)
    oracle_node_limit: int = DEFAULT_NODE_LIMIT


def build_default_tiny_cases() -> Tuple[TinyBenchmarkCase, ...]:
    return (
        TinyBenchmarkCase(
            slug="tiny-sgs-single-machine",
            objective_name="min_overdue",
            batches=(
                TinyBatchSpec(batch_id="batch-a", due_date="2026-01-05", priority="normal"),
                TinyBatchSpec(batch_id="batch-b", due_date="2026-01-05", priority="normal"),
            ),
            operations=(
                TinyOperationSpec(
                    op_id=1,
                    op_code="STEP-A1",
                    batch_id="batch-a",
                    seq=1,
                    machine_id="machine-main",
                    operator_id="operator-main",
                    duration_hours=1.0,
                    op_type_name="turning",
                ),
                TinyOperationSpec(
                    op_id=2,
                    op_code="STEP-B1",
                    batch_id="batch-b",
                    seq=1,
                    machine_id="machine-main",
                    operator_id="operator-main",
                    duration_hours=2.0,
                    op_type_name="turning",
                ),
            ),
            dispatch_mode="sgs",
            dispatch_rule="slack",
        ),
    )
