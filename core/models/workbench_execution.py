"""Public execution ledger DTOs. No database keys or internal revision numbers."""

from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional

_IMMUTABLE_SCALARS = frozenset((str, int, float, bool, bytes, type(None)))


def _snapshot_value(value: Any) -> Any:
    # Python 3.8 asdict calls deepcopy for every immutable scalar. A ledger read
    # serializes thousands of projections several times for its existing size
    # guards and response; these scalars need no copying. Mutable children still
    # receive independent snapshots, including report histories and write tokens.
    if type(value) in _IMMUTABLE_SCALARS:
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _snapshot_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return type(value)(*(_snapshot_value(item) for item in value))
    if isinstance(value, (list, tuple)):
        return type(value)(_snapshot_value(item) for item in value)
    if isinstance(value, dict):
        return type(value)((_snapshot_value(key), _snapshot_value(item)) for key, item in value.items())
    return deepcopy(value)


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
        return _snapshot_value(self)


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
    voided_reports: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _snapshot_value(self)
