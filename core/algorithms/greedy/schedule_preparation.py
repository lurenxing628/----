"""Fixed native inputs owned by one scheduling operation or search session."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Set, Tuple, Union

from core.algorithm_contracts.resource_occupancy import PreparedSeedApplication, ResourceOccupancy
from core.algorithm_contracts.sort_strategies import BatchForSort, SortStrategy, StrategyFactory
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_runtime.checkpoint_calendar import (
    checkpoint_calendar_signature,
    unsupported_calendar,
)
from core.algorithm_runtime.checkpoint_inputs import input_record, input_value
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithm_runtime.resource_demand import ResourceClaim
from core.errors import ValidationError
from core.models.batch import Batch
from core.shared.strict_parse import parse_optional_date, parse_optional_datetime

if TYPE_CHECKING:
    from .dispatch.sgs_graph import PreparedGraphReadyTopology

_NO_PLACED_GROUPS = MappingProxyType({})


@dataclass
class NativeSchedulePreparation:
    normalized_machine_downtimes: Dict[str, List[Tuple[datetime, datetime]]]
    calendar: Any
    operations: List[OpForScheduleAlgo]
    records_by_token: Dict[int, Any]
    batches: Dict[str, Batch]
    seed_results: List[ScheduleResult]
    seed_applications: Tuple[PreparedSeedApplication, ...]
    seed_occupancies_by_op_id: Mapping[int, Tuple[ResourceOccupancy, ...]]
    seed_external_group_cache: Dict[Any, Any]
    seed_op_ids: Set[int]
    unseeded_operations: List[OpForScheduleAlgo]
    resource_pool: Any
    graph_ready_context: Any
    warnings: Tuple[str, ...]
    algo_stats: Dict[str, Any]
    # Compiled once from graph_ready_context; None exactly when the run has no graph input.
    topology: Optional[PreparedGraphReadyTopology]
    score_cache_factory: Any = None
    resource_candidates: Dict[Any, Any] = field(default_factory=dict)
    resource_claims: Dict[int, Any] = field(default_factory=dict)
    piece_batches: Dict[int, Any] = field(default_factory=dict)
    total_hours_by_op_id: Dict[int, float] = field(default_factory=dict)
    average_internal_proc_hours: Optional[float] = None
    _variant_operations: List[OpForScheduleAlgo] = field(default_factory=list)
    _batch_sort_inputs: Dict[SortStrategy, Tuple[BatchForSort, ...]] = field(
        default_factory=dict, init=False, repr=False
    )
    _batch_orders: Dict[Tuple[Any, ...], Tuple[str, ...]] = field(
        default_factory=dict, init=False, repr=False
    )
    _parsed_due_dates: Dict[str, Optional[date]] = field(
        default_factory=dict, init=False, repr=False
    )
    _all_due_dates_parsed: bool = field(default=False, init=False, repr=False)
    _batch_due_dates_valid: Optional[bool] = field(default=None, init=False, repr=False)
    _parsed_created_at: Optional[Dict[str, Optional[datetime]]] = field(
        default=None, init=False, repr=False
    )
    _parsed_ready_starts: Optional[Dict[str, Optional[datetime]]] = field(
        default=None, init=False, repr=False
    )
    _certified_external_by_op_id: Dict[int, bool] = field(
        default_factory=dict, init=False, repr=False
    )
    # The run context points back at this preparation, so prepare_native_schedule_inputs sets it once.
    run_context: Any = field(init=False, repr=False, compare=False)
    _calendar_signature: Any = field(init=False, repr=False, default=None)
    _checkpoint_parts: Any = field(init=False, repr=False, default=None)

    def graph_topology(self) -> PreparedGraphReadyTopology:
        """The compiled graph facts every graph-mode consumer shares, including its schedulable id set."""
        if self.topology is None:
            raise ValueError("本次排产没有图输入，不能按图模式解码或搜索。")
        return self.topology

    def parsed_due_dates(self) -> Dict[str, Optional[date]]:
        if not self._all_due_dates_parsed:
            for batch_id, batch in self.batches.items():
                if batch_id not in self._parsed_due_dates:
                    self._parsed_due_dates[batch_id] = parse_optional_date(batch.due_date, field="due_date")
            self._all_due_dates_parsed = True
            self._batch_due_dates_valid = True
        return self._parsed_due_dates

    def due_date_for_batch(self, batch_id: str, batch: Batch) -> Optional[date]:
        if batch_id in self._parsed_due_dates and (
            self._all_due_dates_parsed or self.batches.get(batch_id) is batch
        ):
            return self._parsed_due_dates[batch_id]
        parsed = parse_optional_date(batch.due_date, field="due_date")
        if self.batches.get(batch_id) is batch:
            self._parsed_due_dates[batch_id] = parsed
        return parsed

    def all_batch_due_dates_valid(self) -> bool:
        if self._batch_due_dates_valid is None:
            try:
                self.parsed_due_dates()
            except ValidationError:
                self._batch_due_dates_valid = False
            else:
                self._batch_due_dates_valid = True
        return self._batch_due_dates_valid

    def parsed_created_at(self) -> Dict[str, Optional[datetime]]:
        if self._parsed_created_at is None:
            self._parsed_created_at = {
                batch_id: parse_optional_datetime(batch.created_at, field="created_at")
                for batch_id, batch in self.batches.items()
            }
        return self._parsed_created_at

    def parsed_ready_starts(self) -> Dict[str, Optional[datetime]]:
        if self._parsed_ready_starts is None:
            ready_starts: Dict[str, Optional[datetime]] = {}
            for batch_id, batch in self.batches.items():
                ready_date = parse_optional_date(batch.ready_date, field="ready_date")
                ready_starts[batch_id] = (
                    datetime(ready_date.year, ready_date.month, ready_date.day, 0, 0, 0)
                    if ready_date is not None
                    else None
                )
            self._parsed_ready_starts = ready_starts
        return self._parsed_ready_starts

    def batch_sort_inputs(self, *, strategy: SortStrategy) -> Tuple[BatchForSort, ...]:
        cached = self._batch_sort_inputs.get(strategy)
        if cached is None:
            created_at: Optional[Dict[str, Optional[datetime]]]
            if strategy == SortStrategy.FIFO and not self._all_due_dates_parsed and self._parsed_created_at is None:
                due_dates: Dict[str, Optional[date]] = {}
                parsed_created: Dict[str, Optional[datetime]] = {}
                for batch_id, batch in self.batches.items():
                    due_dates[batch_id] = (
                        self._parsed_due_dates[batch_id]
                        if batch_id in self._parsed_due_dates
                        else parse_optional_date(batch.due_date, field="due_date")
                    )
                    parsed_created[batch_id] = parse_optional_datetime(batch.created_at, field="created_at")
                self._parsed_due_dates.update(due_dates)
                self._all_due_dates_parsed = True
                self._batch_due_dates_valid = True
                self._parsed_created_at = parsed_created
                created_at = parsed_created
            else:
                due_dates = self.parsed_due_dates()
                created_at = self.parsed_created_at() if strategy == SortStrategy.FIFO else None
            cached = tuple(
                BatchForSort(
                    batch_id=batch_id,
                    priority=batch.priority,
                    due_date=due_dates[batch_id],
                    created_at=created_at[batch_id] if created_at is not None else None,
                )
                for batch_id, batch in self.batches.items()
            )
            self._batch_sort_inputs[strategy] = cached
        return cached

    def batch_order(
        self,
        *,
        start_dt: Union[datetime, date],
        strategy: SortStrategy,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, ...]:
        base_date = start_dt.date() if isinstance(start_dt, datetime) else start_dt
        raw_params = params or {}
        normalized_params = (
            (
                float(raw_params.get("priority_weight", 0.4)),
                float(raw_params.get("due_weight", 0.5)),
            )
            if strategy == SortStrategy.WEIGHTED
            else ()
        )
        key = (strategy, base_date, normalized_params)
        cached = self._batch_orders.get(key)
        if cached is None:
            sortable = self.batch_sort_inputs(strategy=strategy)
            sorter = StrategyFactory.create(strategy, **raw_params)
            cached = tuple(item.batch_id for item in sorter.sort(sortable, base_date=base_date))
            self._batch_orders[key] = cached
        return cached

    def certified_external_operation(self, op: OpForScheduleAlgo) -> bool:
        cached = self._certified_external_by_op_id.get(op.id)
        if cached is not None:
            return cached
        from .dispatch.sgs_due_span import external_candidate_window

        try:
            external_candidate_window(self.calendar, _NO_PLACED_GROUPS, op=op, prev_end=datetime.min)
        except (ValidationError, ValueError, OverflowError):
            cached = False
        else:
            cached = True
        self._certified_external_by_op_id[op.id] = cached
        return cached

    def operation_batch(self, op: OpForScheduleAlgo, batch: Batch) -> Batch:
        if op.piece_id is None:
            return batch
        token = id(batch)
        if token not in self.piece_batches:
            self.piece_batches[token] = operation_batch(op, batch)
        return self.piece_batches[token]

    def resource_candidates_for(self, op: OpForScheduleAlgo) -> Any:
        from .auto_assign import fixed_resource_inputs, prepare_resource_candidates
        key = fixed_resource_inputs(op)
        if key not in self.resource_candidates:
            self.resource_candidates[key] = prepare_resource_candidates(op, self.resource_pool)
        return self.resource_candidates[key]

    def qualified_resource_pairs(self, op: OpForScheduleAlgo) -> Any:
        return self.resource_candidates_for(op).pairs

    def eligible_auto_assign_resources(self, op: OpForScheduleAlgo) -> Any:
        return self.resource_candidates_for(op).eligible_resources

    def resource_claim_for(self, op: OpForScheduleAlgo) -> Any:
        token = id(op)
        if token in self.resource_claims:
            return self.resource_claims[token]
        claim = None
        op_id, batch_id, piece = op.id, op.batch_id, op.piece_id
        source = str(op.source or "internal").strip().lower()
        # A zero-hour operation is a point event and claims no resource time. Only operations whose batch is
        # missing lack prepared hours; dispatch retires them before any placement is compared.
        point_event = self.total_hours_by_op_id.get(op_id) == 0.0
        if (type(op_id) is int and op_id > 0 and type(batch_id) in (str, int) and batch_id and not point_event
                and source == "internal" and (piece is None or (type(piece) is str and piece and piece.strip() == piece))):
            pairs = frozenset(self.qualified_resource_pairs(op))
            claim = ResourceClaim(token, op_id, str(batch_id).strip(), (str(batch_id).strip(), piece), pairs,
                                  Counter(mid for mid, _ in pairs), Counter(oid for _, oid in pairs))
        if token in self.records_by_token:
            self.resource_claims[token] = claim
        return claim

    def register_operation_variant(self, variant_op: OpForScheduleAlgo) -> None:
        variant_token = id(variant_op)
        self.records_by_token[variant_token] = variant_op
        if self._checkpoint_parts is not None:
            self._checkpoint_parts["operations"][variant_token] = input_record(variant_op, field="operations")
        else:
            self._variant_operations.append(variant_op)
        self.resource_claim_for(variant_op)

    def checkpoint_calendar_component(self) -> Tuple[Any, ...]:
        if self._calendar_signature is None:
            raw_signature = checkpoint_calendar_signature(self.calendar)
            try:
                self._calendar_signature = input_value(raw_signature, field="calendar_signature")
            except ValidationError:
                unsupported_calendar()
        return self._calendar_signature

    def checkpoint_fixed_parts(self) -> Dict[str, Any]:
        """Encode fixed checkpoint records lazily; ordinary full decodes never need them."""
        if self._checkpoint_parts is None:
            from .dispatch.sgs_checkpoint import seed_signature
            self._checkpoint_parts = {
                "operations": {
                    id(op): input_record(op, field="operations")
                    for op in list(self.unseeded_operations) + self._variant_operations
                },
                "batches": tuple((key, input_record(batch, field="batches")) for key, batch in self.batches.items()),
                "downtimes": input_value(self.normalized_machine_downtimes, field="machine_downtimes"),
                "resources": input_value(self.resource_pool, field="resource_pool"),
                "seeds": tuple(seed_signature(result) for result in self.seed_results),
                "contexts": {},
            }
        return self._checkpoint_parts
