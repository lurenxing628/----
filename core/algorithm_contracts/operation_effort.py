"""The standard requirement used by one run, before calendar conversion."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

from core.models.enums import OperationQuantityBasis, OperationRequirementRole, OperationSetupState

RUNTIME_REQUIREMENT_BASIS = "runtime_requirement_v1"


@dataclass(frozen=True)
class OperationEffort:
    op_id: Optional[int]
    batch_id: Optional[str]
    piece_id: Optional[str]
    source: str
    target_quantity: Optional[float]
    remaining_quantity: Optional[int]
    setup_standard_hours: Optional[float]
    processing_standard_hours: Optional[float]
    required_standard_hours: Optional[float]
    setup_state: str = OperationSetupState.UNKNOWN.value
    requirement_role: str = OperationRequirementRole.NEW_SCHEDULE.value
    quantity_basis: str = OperationQuantityBasis.UNKNOWN.value
    execution_target_quantity: Optional[int] = None
    execution_quantity_basis: str = OperationQuantityBasis.UNKNOWN.value
    external_cycle_days: Optional[float] = None
    external_group_id: Optional[str] = None
    external_merge_mode: Optional[str] = None
    effort_basis: str = RUNTIME_REQUIREMENT_BASIS
    data_gaps: Tuple[Dict[str, str], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["data_gaps"] = list(result["data_gaps"])
        return result
