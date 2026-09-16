from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.ordering import normalize_text_id
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL

from .owned_timeline import OwnedTimeline, clone_timeline
from .resource_quality import MachineTypeState
from .runtime_state import accumulate_busy_hours, update_machine_last_state


@dataclass
class ScheduleRunState:
    base_time: datetime
    batch_progress: Dict[str, datetime] = field(default_factory=dict)
    external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]] = field(default_factory=dict)
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]] = field(default_factory=OwnedTimeline)
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]] = field(default_factory=OwnedTimeline)
    machine_busy_hours: Dict[str, float] = field(default_factory=dict)
    operator_busy_hours: Dict[str, float] = field(default_factory=dict)
    last_op_type_by_machine: Dict[str, str] = field(default_factory=MachineTypeState)
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
    failure_details: List[Dict[str, Any]] = field(default_factory=list)
    batch_failure_sources: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_legacy(
        cls,
        *,
        base_time: datetime,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
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

    def clone(self) -> ScheduleRunState:
        """Independent snapshot for a decode checkpoint.

        Result rows and failure detail dicts are never mutated after they are
        recorded, so they are shared; every container that dispatch appends to
        is copied. A run-owned type state is cloned without its live demand; the
        resumed decode rebuilds and replays it for its own operation objects.
        """
        types = self.last_op_type_by_machine
        return ScheduleRunState(
            base_time=self.base_time,
            batch_progress=dict(self.batch_progress),
            external_group_cache=dict(self.external_group_cache),
            machine_timeline=clone_timeline(self.machine_timeline),
            operator_timeline=clone_timeline(self.operator_timeline),
            machine_busy_hours=dict(self.machine_busy_hours),
            operator_busy_hours=dict(self.operator_busy_hours),
            last_op_type_by_machine=types.clone() if isinstance(types, MachineTypeState) else dict(types),
            last_end_by_machine=dict(self.last_end_by_machine),
            results=list(self.results),
            errors=list(self.errors),
            blocked_batches=set(self.blocked_batches),
            initial_scheduled_count=int(self.initial_scheduled_count or 0),
            failed_count=int(self.failed_count or 0),
            seed_count=int(self.seed_count or 0),
            missing_seed_machine_count=int(self.missing_seed_machine_count or 0),
            missing_seed_operator_count=int(self.missing_seed_operator_count or 0),
            missing_seed_machine_samples=list(self.missing_seed_machine_samples),
            missing_seed_operator_samples=list(self.missing_seed_operator_samples),
            failure_details=list(self.failure_details),
            batch_failure_sources=dict(self.batch_failure_sources),
        )

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
        if isinstance(self.last_op_type_by_machine, MachineTypeState):
            self.last_op_type_by_machine.complete(result.op_id)

    def record_dispatch_failure(
        self,
        batch_id: str,
        *,
        block: bool,
        remaining_failed: int = 0,
        failed_op: Optional[Any] = None,
        skipped_ops: Optional[List[Any]] = None,
    ) -> None:
        self.failed_count += 1 + max(int(remaining_failed or 0), 0)
        if failed_op is not None:
            detail = self._failure_detail("dispatch_operation_failed", failed_op, batch_id=batch_id)
            self.failure_details.append(detail)
            self._retire_resource_demand(detail["op_id"])
            if batch_id:
                self.batch_failure_sources[batch_id] = detail
        for skipped_op in list(skipped_ops or []):
            self.failure_details.append(
                self._failure_detail(
                    "skipped_after_batch_failure",
                    skipped_op,
                    batch_id=batch_id,
                    failed_source=self.batch_failure_sources.get(batch_id),
                )
            )
        if block and batch_id:
            self.blocked_batches.add(batch_id)
            if isinstance(self.last_op_type_by_machine, MachineTypeState):
                self.last_op_type_by_machine.block_batch(batch_id)

    def record_missing_batch(self, op: Any, batch_id: str) -> None:
        self.failed_count += 1
        # 失败的用户可见文案统一由结构化 failure_details + _structured_failure_message 单点渲染。
        # 不再往 state.errors 塞原始中文串：它不匹配任何 legacy 反解模式，会回落成
        # generic_scheduler_error（“请联系管理员”），与具体文案并列形成双发并虚增 error_count。
        detail = self._failure_detail("missing_batch", op, batch_id=batch_id)
        self.failure_details.append(detail)
        self._retire_resource_demand(detail["op_id"], blocked_batch=batch_id)

    def record_skipped_after_batch_failure(self, op: Any, batch_id: str, *, count_failure: bool = True) -> None:
        if count_failure:
            self.failed_count += 1
        detail = self._failure_detail(
            "skipped_after_batch_failure", op, batch_id=batch_id,
            failed_source=self.batch_failure_sources.get(batch_id),
        )
        self.failure_details.append(detail)
        self._retire_resource_demand(detail["op_id"])

    def record_graph_fixed_order_conflict(self, op: Any, batch_id: str, *, fixed_successor_op_ids: List[int]) -> None:
        # 审计 A02：后道工序已报工（PROCESSING/PAUSED 进固定集）但前道排产失败，
        # 报工顺序与工艺顺序不一致。只补结构化明细留痕、不重复计数——失败工序
        # 自身已由 record_dispatch_failure / record_dispatch_exception 计 1。
        self.failure_details.append(
            self._failure_detail(
                "graph_fixed_successor_order_conflict",
                op,
                batch_id=batch_id,
                extra={"fixed_successor_op_ids": [int(item) for item in list(fixed_successor_op_ids or [])][:20]},
            )
        )

    def record_graph_blocked_after_failure(self, op: Any, batch_id: str, *, failed_op: Any) -> None:
        detail = self._failure_detail(
            "graph_blocked_after_failure", op, batch_id=batch_id,
            failed_source=self._op_identity(failed_op),
        )
        self.failure_details.append(detail)
        self._retire_resource_demand(detail["op_id"])

    def record_dispatch_exception(self, op: Any, batch_id: str, *, dispatch_mode: str) -> None:
        self.failed_count += 1
        # 同 record_missing_batch：只写结构化明细，渲染交给 _structured_failure_message，避免双发。
        detail = self._failure_detail(
            "dispatch_operation_exception",
            op,
            batch_id=batch_id,
            extra={"dispatch_mode": str(dispatch_mode or "").strip()},
        )
        self.failure_details.append(detail)
        self._retire_resource_demand(detail["op_id"], blocked_batch=batch_id)
        if batch_id:
            self.batch_failure_sources[batch_id] = detail
            self.blocked_batches.add(batch_id)

    def _retire_resource_demand(self, op_id: int, *, blocked_batch: str = "") -> None:
        if isinstance(self.last_op_type_by_machine, MachineTypeState):
            self.last_op_type_by_machine.complete(op_id)
            if blocked_batch:
                self.last_op_type_by_machine.block_batch(blocked_batch)

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
            start_time=result.start_time,
            op_id=result.op_id,
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

    def _failure_detail(
        self,
        code: str,
        op: Any,
        *,
        batch_id: str,
        failed_source: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        detail = self._op_identity(op)
        detail.update({"code": str(code), "batch_id": normalize_text_id(batch_id) or detail.get("batch_id")})
        if failed_source:
            detail["failed_op_id"] = failed_source.get("op_id")
            detail["failed_op_code"] = failed_source.get("op_code")
        if extra:
            detail.update(dict(extra))
        return detail

    @staticmethod
    def _op_identity(op: Any) -> Dict[str, Any]:
        try:
            op_id = int(getattr(op, "id", 0) or getattr(op, "op_id", 0) or 0)
        except Exception:
            op_id = 0
        try:
            seq = int(getattr(op, "seq", 0) or 0)
        except Exception:
            seq = 0
        return {
            "op_id": op_id,
            "op_code": normalize_text_id(ScheduleRunState._safe_text_attr(op, "op_code", "")),
            "batch_id": normalize_text_id(ScheduleRunState._safe_text_attr(op, "batch_id", "")),
            "seq": seq,
        }

    @staticmethod
    def _safe_text_attr(op: Any, name: str, default: str) -> str:
        try:
            return str(getattr(op, name, default) or default)
        except Exception:
            return str(default or "")
