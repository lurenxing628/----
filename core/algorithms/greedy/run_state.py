from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.algorithms.ordering import normalize_text_id
from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import INTERNAL

from .dispatch.runtime_state import accumulate_busy_hours, update_machine_last_state


@dataclass
class ScheduleRunState:
    base_time: datetime
    batch_progress: Dict[str, datetime] = field(default_factory=dict)
    external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]] = field(default_factory=dict)
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]] = field(default_factory=dict)
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]] = field(default_factory=dict)
    machine_busy_hours: Dict[str, float] = field(default_factory=dict)
    operator_busy_hours: Dict[str, float] = field(default_factory=dict)
    last_op_type_by_machine: Dict[str, str] = field(default_factory=dict)
    last_end_by_machine: Dict[str, datetime] = field(default_factory=dict)
    results: List[ScheduleResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    blocked_batches: set = field(default_factory=set)
    initial_scheduled_count: int = 0
    failed_count: int = 0
    seed_count: int = 0
    missing_seed_machine_count: int = 0
    missing_seed_operator_count: int = 0
    missing_seed_machine_samples: List[str] = field(default_factory=list)
    missing_seed_operator_samples: List[str] = field(default_factory=list)

    @classmethod
    def from_legacy(
        cls,
        *,
        base_time: datetime,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        last_op_type_by_machine: Dict[str, str],
        last_end_by_machine: Dict[str, datetime],
        results: List[ScheduleResult],
        errors: List[str],
        blocked_batches: set,
        scheduled_count: int,
        failed_count: int,
    ) -> ScheduleRunState:
        initial_scheduled_count = max(int(scheduled_count or 0) - len(results or []), 0)
        return cls(
            base_time=base_time,
            batch_progress=batch_progress,
            external_group_cache=external_group_cache,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            last_op_type_by_machine=last_op_type_by_machine,
            last_end_by_machine=last_end_by_machine,
            results=results,
            errors=errors,
            blocked_batches=blocked_batches,
            initial_scheduled_count=initial_scheduled_count,
            failed_count=int(failed_count or 0),
        )

    @property
    def scheduled_count(self) -> int:
        return int(self.initial_scheduled_count or 0) + len(self.results)

    def prev_end(self, batch_id: str) -> datetime:
        return self.batch_progress.get(batch_id, self.base_time)

    def advance_batch(self, batch_id: str, end_time: Optional[datetime]) -> None:
        if not batch_id or not isinstance(end_time, datetime):
            return
        self.batch_progress[batch_id] = max(self.batch_progress.get(batch_id, self.base_time), end_time)

    def record_seed_result(self, result: ScheduleResult) -> None:
        self.results.append(result)
        self.seed_count += 1
        self.advance_batch(normalize_text_id(result.batch_id), result.end_time)
        self._record_internal_usage(result, seed_mode=True)
        if (result.source or "").strip().lower() == INTERNAL:
            self._record_missing_seed_resources(result)

    def record_dispatch_success(self, result: ScheduleResult) -> None:
        self.results.append(result)
        self.advance_batch(normalize_text_id(result.batch_id), result.end_time)
        self._record_internal_usage(result, seed_mode=False)

    def record_dispatch_failure(self, batch_id: str, *, block: bool, remaining_failed: int = 0) -> None:
        self.failed_count += 1 + max(int(remaining_failed or 0), 0)
        if block and batch_id:
            self.blocked_batches.add(batch_id)

    def seed_resource_warnings(self) -> List[str]:
        warnings: List[str] = []
        if self.missing_seed_machine_count:
            sample = ", ".join([x for x in self.missing_seed_machine_samples if x and x != "?"][:5])
            warnings.append(
                f"沿用旧排产结果时发现自制工序缺少设备：{self.missing_seed_machine_count} 条"
                f"{('（示例工序编号：' + sample + '）') if sample else ''}。系统已尽量沿用可确认的时间安排，但这些工序不能锁定设备资源。"
            )
        if self.missing_seed_operator_count:
            sample = ", ".join([x for x in self.missing_seed_operator_samples if x and x != "?"][:5])
            warnings.append(
                f"沿用旧排产结果时发现自制工序缺少人员：{self.missing_seed_operator_count} 条"
                f"{('（示例工序编号：' + sample + '）') if sample else ''}。系统已尽量沿用可确认的时间安排，但这些工序不能锁定人员资源。"
            )
        return warnings

    def _record_internal_usage(self, result: ScheduleResult, *, seed_mode: bool) -> None:
        if (result.source or "").strip().lower() != INTERNAL:
            return
        if not isinstance(result.start_time, datetime) or not isinstance(result.end_time, datetime):
            return
        machine_id = normalize_text_id(result.machine_id)
        operator_id = normalize_text_id(result.operator_id)
        accumulate_busy_hours(
            machine_busy_hours=self.machine_busy_hours,
            operator_busy_hours=self.operator_busy_hours,
            machine_id=machine_id,
            operator_id=operator_id,
            start_time=result.start_time,
            end_time=result.end_time,
        )
        update_machine_last_state(
            last_end_by_machine=self.last_end_by_machine,
            last_op_type_by_machine=self.last_op_type_by_machine,
            machine_id=machine_id,
            end_time=result.end_time,
            op_type_name=result.op_type_name,
            seed_mode=bool(seed_mode),
        )

    def _record_missing_seed_resources(self, result: ScheduleResult) -> None:
        op_id = normalize_text_id(getattr(result, "op_id", "") or "?") or "?"
        if not normalize_text_id(result.machine_id):
            self.missing_seed_machine_count += 1
            if len(self.missing_seed_machine_samples) < 5:
                self.missing_seed_machine_samples.append(op_id)
        if not normalize_text_id(result.operator_id):
            self.missing_seed_operator_count += 1
            if len(self.missing_seed_operator_samples) < 5:
                self.missing_seed_operator_samples.append(op_id)
