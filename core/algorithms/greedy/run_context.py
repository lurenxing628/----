from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.auto_assign_contract import AutoAssignAttempt
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse
from core.models.batch import Batch

from .auto_assign import auto_assign_internal_resources_attempt
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation

if TYPE_CHECKING:
    from .dispatch.sgs_score_cache import SgsScoreCache
    from .dispatch.sgs_scoring import SgsCandidateScore
    from .schedule_preparation import NativeSchedulePreparation


@dataclass
class ScheduleRunContext:
    native_preparation: NativeSchedulePreparation
    algo_stats: Dict[str, Any]
    # Per-decode SGS dispatch-key cache and segment-overlap cache owned by this run; None outside SGS.
    sgs_score_cache: Optional[SgsScoreCache]
    overlap_reuse: Optional[SlotOverlapReuse]

    @property
    def calendar(self) -> Any:
        return self.native_preparation.calendar

    @property
    def timing_calendar(self) -> Any:
        cache = self.sgs_score_cache
        if cache is not None and cache.timing is not None:
            return cache.timing
        return self.native_preparation.calendar

    def increment(self, key: str) -> None:
        increment_counter(self.algo_stats, key)

    def schedule_external(
        self,
        *,
        op: OpForScheduleAlgo,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
        base_time: datetime,
        end_dt_exclusive: Optional[datetime],
    ) -> Tuple[Optional[ScheduleResult], Optional[Dict[str, Any]]]:
        return schedule_external(
            calendar=self.calendar,
            op=op,
            batch_progress=batch_progress,
            external_group_cache=external_group_cache,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
        )

    def schedule_internal(
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
        auto_assign_enabled: bool,
        resource_pool: Optional[Dict[str, Any]],
        last_op_type_by_machine: MachineTypeState,
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        scored: Optional[SgsCandidateScore],
    ) -> Tuple[Optional[ScheduleResult], Optional[Dict[str, Any]]]:
        return schedule_internal_operation(
            calendar=self.timing_calendar,
            algo_stats=self.algo_stats,
            auto_assign_resources=self.auto_assign_internal_resources_attempt,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            total_hours_by_op_id=self.native_preparation.total_hours_by_op_id,
            scored=scored,
            overlap_reuse=self.overlap_reuse,
            score_cache=self.sgs_score_cache,
        )

    def auto_assign_internal_resources_attempt(
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
        last_op_type_by_machine: MachineTypeState,
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        probe_only: bool = False,
    ) -> AutoAssignAttempt:
        return auto_assign_internal_resources_attempt(
            calendar=self.timing_calendar,
            algo_stats=self.algo_stats,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            resource_pool=resource_pool,
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            probe_only=probe_only,
            resource_preparation=self.native_preparation,
            overlap_reuse=self.overlap_reuse,
            score_cache=self.sgs_score_cache,
        )

