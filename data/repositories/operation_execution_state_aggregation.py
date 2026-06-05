from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, cast

from core.models.operation_execution_event import OperationExecutionEvent
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.operation_execution_state import OperationExecutionState
from core.models.resource_identity import ResourceIdentity, build_resource_identity

from .operation_execution_state_builder import build_operation_execution_state


def _event_scope(event: OperationExecutionEvent) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=event.schedule_version,
        schedule_id=event.schedule_id,
        op_id=event.op_id,
        batch_id=event.batch_id,
        source_table=event.source_table,
        effective_plan_role=event.effective_plan_role,
        scenario_id=event.scenario_id,
    )


def _resource_identity(resource_id: Any, resource_name: Any) -> ResourceIdentity:
    return build_resource_identity(resource_id=resource_id, resource_name=resource_name)


class _StateAggregationHost(Protocol):
    def list_events_by_scopes(self, scopes: Sequence[OperationExecutionScope]) -> List[OperationExecutionEvent]: ...

    def fetchall(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]: ...


class OperationExecutionStateAggregationMixin:
    def aggregate_states_by_scopes(
        self,
        scopes: Sequence[OperationExecutionScope],
    ) -> Dict[OperationExecutionScope, OperationExecutionState]:
        repo = cast(_StateAggregationHost, self)
        normalized = list(dict.fromkeys(scopes or ()))
        events_by_scope: Dict[OperationExecutionScope, List[OperationExecutionEvent]] = {
            scope: [] for scope in normalized
        }
        for event in repo.list_events_by_scopes(normalized):
            scope = _event_scope(event)
            events_by_scope.setdefault(scope, []).append(event)

        machine_resources = self._machine_resources(self._machine_ids(events_by_scope))
        operator_resources = self._operator_resources(self._operator_ids(events_by_scope))
        return {
            scope: self._aggregate_single_state(
                op_id=scope.op_id,
                batch_id=scope.batch_id,
                events=events_by_scope.get(scope) or [],
                machine_resources=machine_resources,
                operator_resources=operator_resources,
            )
            for scope in normalized
        }

    def state_revision_for_scope(self, scope: OperationExecutionScope) -> str:
        state = self.aggregate_states_by_scopes([scope]).get(scope)
        return state.state_revision if state is not None else f"{int(scope.op_id)}:0:0"

    def _machine_resources(self, machine_ids: Sequence[str]) -> Dict[str, ResourceIdentity]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in machine_ids) if item]
        if not ids:
            return {}
        repo = cast(_StateAggregationHost, self)
        out: Dict[str, ResourceIdentity] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = repo.fetchall(
                f"SELECT machine_id, name FROM Machines WHERE machine_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                machine_id = str(row.get("machine_id") or "")
                out[machine_id] = _resource_identity(machine_id, row.get("name"))
        return out

    def _operator_resources(self, operator_ids: Sequence[str]) -> Dict[str, ResourceIdentity]:
        ids = [item for item in dict.fromkeys(str(x or "").strip() for x in operator_ids) if item]
        if not ids:
            return {}
        repo = cast(_StateAggregationHost, self)
        out: Dict[str, ResourceIdentity] = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i : i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            rows = repo.fetchall(
                f"SELECT operator_id, name FROM Operators WHERE operator_id IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                operator_id = str(row.get("operator_id") or "")
                out[operator_id] = _resource_identity(operator_id, row.get("name"))
        return out

    @staticmethod
    def _machine_ids(events_by_scope: Mapping[Any, List[OperationExecutionEvent]]) -> List[str]:
        out: List[str] = []
        for events in events_by_scope.values():
            for event in events:
                for value in (event.actual_machine_id, event.affected_machine_id):
                    if value:
                        out.append(str(value))
        return out

    @staticmethod
    def _operator_ids(events_by_scope: Mapping[Any, List[OperationExecutionEvent]]) -> List[str]:
        out: List[str] = []
        for events in events_by_scope.values():
            for event in events:
                for value in (event.actual_operator_id, event.affected_operator_id):
                    if value:
                        out.append(str(value))
        return out

    def _aggregate_single_state(
        self,
        *,
        op_id: int,
        batch_id: Optional[str],
        events: List[OperationExecutionEvent],
        machine_resources: Dict[str, ResourceIdentity],
        operator_resources: Dict[str, ResourceIdentity],
    ) -> OperationExecutionState:
        return build_operation_execution_state(
            op_id=op_id,
            batch_id=batch_id,
            events=events,
            machine_resources=machine_resources,
            operator_resources=operator_resources,
        )


__all__ = ["OperationExecutionStateAggregationMixin"]
