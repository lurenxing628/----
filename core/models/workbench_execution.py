"""Public execution ledger DTOs. No database keys or internal revision numbers."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProductionReport:
    report_ref: str
    report_no: str
    operation_ref: str
    recorded_against_task_ref: str
    recorded_against_plan_ref: str
    source: str
    actual_start: Optional[str]
    actual_end: Optional[str]
    completed_quantity: Optional[int]
    effective_processing_hours: Optional[float]
    actual_machine_ref: Optional[str]
    actual_operator_ref: Optional[str]
    remark: str
    recorded_at: str
    correction_history: List[Dict[str, Any]]
    write_context: Dict[str, Any]
    revision_ref: str
    legacy_fact_ref: Optional[str] = None
    local_operator: str = ""
    declared_operator: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionProjection:
    operation_ref: str
    current_task_ref: Optional[str]
    comparison_task_ref: Optional[str]
    plan_identity: Optional[Dict[str, Any]]
    target_quantity: Optional[int]
    target_basis: str
    known_completed_quantity: int
    quantity_complete: bool
    unknown_record_count: int
    records_complete: bool
    first_actual_start: Optional[str]
    confirmed_finish: Optional[str]
    execution_state: str
    completion_basis: Optional[str]
    data_quality: str
    reports: List[ProductionReport] = field(default_factory=list)
    legacy_facts: List[Dict[str, Any]] = field(default_factory=list)
    remaining_quantity: Optional[int] = None
    remaining_plan: Optional[Dict[str, Any]] = None
    data_gaps: List[Dict[str, Any]] = field(default_factory=list)
    write_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
