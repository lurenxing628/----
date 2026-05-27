from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo


@dataclass(frozen=True)
class ExecutionFact:
    op_id: int
    batch_id: Optional[str]
    actual_status: str
    actual_start_time: Optional[datetime]
    actual_end_time: Optional[datetime]
    actual_machine_id: Optional[str]
    actual_operator_id: Optional[str]
    last_event_schedule_version: Optional[int]
    last_event_schedule_id: Optional[int]
    state_revision: str


def _positive_op_ids(values: Sequence[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for raw in values or []:
        try:
            op_id = int(raw)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    return out


def _parse_execution_time(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


class ExecutionFactProvider:
    """按工序读取现场执行事实。

    执行事件里的 schedule_id/version 只说明事件提交时用户看到哪版计划；
    重排读取当前现场事实时，以 op_id 为主线。
    """

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.event_repo = OperationExecutionEventRepo(conn, logger=logger)

    def list_by_op_ids(self, op_ids: Sequence[int]) -> List[ExecutionFact]:
        ids = _positive_op_ids(op_ids)
        if not ids:
            return []
        states = self.event_repo.aggregate_states_by_op_ids(ids)
        latest_events = self.event_repo.list_latest_events_by_op_ids(ids)
        facts: List[ExecutionFact] = []
        for op_id in ids:
            state = states.get(int(op_id))
            latest = latest_events.get(int(op_id))
            facts.append(
                ExecutionFact(
                    op_id=int(op_id),
                    batch_id=None if state is None else state.batch_id,
                    actual_status=(
                        EXECUTION_STATUS_NOT_STARTED
                        if state is None
                        else str(state.current_status or EXECUTION_STATUS_NOT_STARTED)
                    ),
                    actual_start_time=None if state is None else _parse_execution_time(state.actual_start_time),
                    actual_end_time=None if state is None else _parse_execution_time(state.actual_end_time),
                    actual_machine_id=None if state is None else state.actual_machine_id,
                    actual_operator_id=None if state is None else state.actual_operator_id,
                    last_event_schedule_version=None if latest is None else int(latest.schedule_version),
                    last_event_schedule_id=None if latest is None else int(latest.schedule_id),
                    state_revision=f"{int(op_id)}:0:0" if state is None else state.state_revision,
                )
            )
        return facts

    def facts_by_op_id(self, op_ids: Sequence[int]) -> Dict[int, ExecutionFact]:
        return {int(fact.op_id): fact for fact in self.list_by_op_ids(op_ids)}


__all__ = ["ExecutionFact", "ExecutionFactProvider"]
