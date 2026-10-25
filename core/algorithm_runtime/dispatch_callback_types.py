from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_runtime.auto_assign_contract import AutoAssignAttempt
from core.models.batch import Batch


class InternalScheduleCallback(Protocol):
    def __call__(
        self,
        *,
        op: OpForScheduleAlgo,
        batch: Batch,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
        auto_assign_enabled: bool,
        resource_pool: Optional[Dict[str, Any]],
        last_op_type_by_machine: Optional[Dict[str, str]],
        machine_busy_hours: Optional[Dict[str, float]],
        operator_busy_hours: Optional[Dict[str, float]],
    ) -> Tuple[Optional[ScheduleResult], bool]: ...


class ExternalScheduleCallback(Protocol):
    def __call__(
        self,
        *,
        op: OpForScheduleAlgo,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
    ) -> Tuple[Optional[ScheduleResult], bool]: ...


class AutoAssignAttemptCallback(Protocol):
    def __call__(
        self,
        *,
        op: OpForScheduleAlgo,
        batch: Batch,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
        resource_pool: Dict[str, Any],
        last_op_type_by_machine: Dict[str, str],
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        probe_only: bool = False,
    ) -> Union[AutoAssignAttempt, Tuple[str, str], List[str], None]: ...
