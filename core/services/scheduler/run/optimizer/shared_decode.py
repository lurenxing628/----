"""One request ledger and real decode boundary for a shared optimizer run."""

from __future__ import annotations

import math
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithm_contracts.ordering import normalize_batch_order_override
from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_runtime.algo_stats import merge_algo_stats
from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.errors import ValidationError

from .shared_archive import ArchiveObservation, CandidateArchiveRef
from .shared_budget import SharedSearchSkip

if TYPE_CHECKING:
    from core.algorithms.greedy.scheduler import GreedyScheduler

_REDECODE_KINDS = {
    "capture_checkpoints": "capture_checkpoints", "validate_trial": "validation_decode",
    "restore_parent": "restore_parent",
}


@dataclass(frozen=True)
class DecodeRequest:
    dispatch_mode: str
    dispatch_rule: str
    base_time: datetime
    end_dt_exclusive: Optional[datetime]
    auto_assign_enabled: bool
    readiness_gate_enabled: bool
    parameter_warnings: Tuple[str, ...]
    batch_order: Tuple[str, ...]
    sort_inputs: Tuple[Any, ...]
    graph_enabled: bool
    score_enabled: bool
    graph_preorder: Tuple[Tuple[int, ...], ...]
    operation_resources: Tuple[Tuple[int, str, str], ...]
    resource_pair_rank: Tuple[Any, ...]


@dataclass
class DecodedEvaluation:
    results: Any
    summary: Any
    metrics: Any
    used_strategy: Any
    used_params: Dict[str, Any]
    algo_stats: Dict[str, Any]
    receipt: Dict[str, Any]
    entry_id: Optional[int] = None
    archive_observation: Any = None

    def archive_ref(self) -> CandidateArchiveRef:
        """The identity the candidate built from this decode carries; its observation is reported once."""
        return CandidateArchiveRef(self.entry_id, self.archive_observation)


@dataclass
class _RequestRecord:
    request_id: int
    request: DecodeRequest
    entry_id: Optional[int] = None
    verified: bool = False
    original_decode_ms: Optional[float] = None
    source_runtime_ms: Optional[float] = None
    source_initial_decode_runtime_ms: Optional[float] = None
    exploration_requested: bool = False
    new_decision_registered: bool = False


def _immutable(value: Any) -> Tuple[Any, ...]:
    """Direct values, preserving meaningful resource order and missing/empty distinctions."""
    if value is None:
        return ("none",)
    if type(value) in (str, bool, int):
        return (type(value).__name__, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError("共享解码输入必须使用有限数值。", field="shared_decode_request")
        return ("float", value)
    if isinstance(value, (date, datetime)):
        return (type(value).__name__, value)
    if isinstance(value, dict):
        rows = [(_immutable(key), _immutable(item)) for key, item in value.items()]
        return ("mapping", tuple(sorted(rows, key=lambda row: repr(row[0]))))
    if isinstance(value, (tuple, list)):
        return ("sequence", tuple(_immutable(item) for item in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_immutable(item) for item in value), key=repr)))
    raise ValidationError("共享解码输入包含不支持的值。", field="shared_decode_request")


class SharedDecodeSession:
    """Keep request identity and costs; completed schedules belong to the archive."""

    def __init__(
        self, *, archive: Any, budget: Any, scheduler: GreedyScheduler, operations: Any, batches: Any,
        seed_results: Any, downtime_map: Any, resource_pool: Any,
        graph_ready_context: Optional[Dict[str, Any]] = None, clock: Callable[[], float],
        started_at: float, deadline: float,
        event_sink: Optional[Callable[[Dict[str, Any]], Optional[int]]] = None,
        evaluation_context: Optional[Any] = None,
    ) -> None:
        from core.algorithms.greedy.scheduler import prepare_native_schedule_inputs

        self.archive, self.budget, self.scheduler = archive, budget, scheduler
        self.operations, self.batches, self.seed_results = operations, batches, seed_results
        self.resource_pool = resource_pool
        self.clock, self.started_at, self.deadline = clock, started_at, deadline
        self.event_sink = event_sink
        self.native_preparation = prepare_native_schedule_inputs(
            downtime_map, scheduler=scheduler, operations=operations, batches=batches,
            seed_results=seed_results, resource_pool=resource_pool, graph_ready_context=graph_ready_context,
        )
        self._normalized_batches = self.native_preparation.batches
        self.evaluation_context = (
            evaluation_context
            if evaluation_context is not None
            else prepare_evaluation_context(
                batches=batches, expected_operations=operations, seed_results=seed_results,
            )
        )
        self._graph_context = self.native_preparation.graph_ready_context
        # An unassigned machine or operator stays None, as in the input operation; changes name real pairs.
        self._base_operation_resources: Dict[int, Tuple[Optional[str], Optional[str]]] = {
            op.id: (op.machine_id, op.operator_id) for op in operations}
        self._operations_by_id = {op.id: op for op in operations}
        self._op_variant_cache: Dict[Tuple[int, str, str], Any] = {}
        self._last_resources_ops: Optional[Tuple[Tuple[Tuple[int, str, str], ...], List[Any]]] = None
        self._operation_ids = {op.id for op in operations}
        self._records: Dict[DecodeRequest, _RequestRecord] = {}
        self._by_id: Dict[int, _RequestRecord] = {}
        self.actual_decoder_calls = 0
        self.new_decisions = 0
        self.reused_decisions = 0
        self.skipped_requests = 0
        self.failed_decoder_calls = 0
        self._execution_counts: Dict[str, int] = {}

    def _request(self, kwargs: Dict[str, Any]) -> Tuple[DecodeRequest, Any, Dict[str, int], Any, Any, Any]:
        from core.algorithms.greedy.dispatch.sgs_graph import graph_priority_key_map
        from core.algorithms.greedy.scheduler import build_batch_order

        from .graph.predecode import graph_priority_preorder

        pair_rank = kwargs.get("resource_pair_rank") or None
        pool = self.native_preparation.resource_pool
        if pair_rank is not None:
            ranks = dict((pool or {}).get("pair_rank") or {})
            ranks.update(pair_rank)
            pool = dict(pool or {}, pair_rank=ranks)
        params = resolve_schedule_params(
            config=self.scheduler.config, strategy=kwargs.get("strategy"),
            strategy_params=kwargs.get("strategy_params"), start_dt=kwargs["start_dt"],
            end_date=kwargs.get("end_date"), dispatch_mode=kwargs.get("dispatch_mode"),
            dispatch_rule=kwargs.get("dispatch_rule"), resource_pool=pool,
        )
        readiness = bool(kwargs.get("readiness_gate_enabled", False))
        override = normalize_batch_order_override(kwargs.get("batch_order_override"), self._normalized_batches)
        full_override = bool(override) and len(override) == len(self._normalized_batches)
        batch_ranks = build_batch_order(self._normalized_batches, params, batch_order_override=override)
        order = tuple(sorted(batch_ranks, key=batch_ranks.__getitem__))
        sort_inputs = () if full_override else (
            params.strategy.value,
            tuple((name, _immutable(params.used_params[name])) for name in ("priority_weight", "due_weight")
                  if name in params.used_params),
        )
        graph_enabled = bool(kwargs.get("graph_enabled", False))
        score_enabled, preorder, context = False, (), None
        if graph_enabled:
            if self._graph_context is None:
                raise ValueError("SharedDecodeSession has no graph input.")
            score_enabled = kwargs.get("graph_score_enabled", False)
            if type(score_enabled) is not bool:
                raise ValidationError("图评分开关 score_enabled 必须是 bool。", field="graph_ready_context")
            keys = kwargs.get("graph_priority_key_by_op_id")
            if score_enabled:
                if not isinstance(keys, dict) or any(type(op_id) is not int for op_id in keys):
                    raise ValidationError("图评分 key 必须覆盖全部待排工序。", field="graph_ready_context")
                keys = graph_priority_key_map(keys, schedulable_ids=self._operation_ids)
                preorder = graph_priority_preorder(keys)
            context = dict(self._graph_context, score_enabled=score_enabled, graph_priority_key_by_op_id=keys)
        resource_changes = kwargs.get("operation_resources")
        resources = (
            tuple(sorted((op_id, machine_id, operator_id) for op_id, (machine_id, operator_id) in resource_changes.items()
                         if (machine_id, operator_id) != self._base_operation_resources.get(op_id)))
            if resource_changes else ()
        )
        operations = self.operations
        if resources:
            if self._last_resources_ops is not None and self._last_resources_ops[0] == resources:
                operations = self._last_resources_ops[1]
            else:
                replacements = {}
                for op_id, machine_id, operator_id in resources:
                    variant_key = (op_id, machine_id, operator_id)
                    variant_op = self._op_variant_cache.get(variant_key)
                    if variant_op is None:
                        base_op = self._operations_by_id[op_id]
                        variant_op = copy(base_op)
                        variant_op.machine_id, variant_op.operator_id = machine_id, operator_id
                        self.native_preparation.register_operation_variant(base_op, variant_op)
                        self._op_variant_cache[variant_key] = variant_op
                    replacements[op_id] = variant_op
                operations = [replacements.get(op.id, op) for op in self.operations]
                self._last_resources_ops = (resources, operations)
        request = DecodeRequest(
            params.dispatch_mode_key, params.dispatch_rule_spec.token, params.base_time, params.end_dt_exclusive,
            params.auto_assign_enabled, readiness, tuple(params.warnings), order, sort_inputs,
            graph_enabled, score_enabled, preorder, resources, _immutable(pair_rank),
        )
        return request, params, batch_ranks, operations, pool, context

    def _decode(self, kwargs: Dict[str, Any], params: Any, batch_order: Dict[str, int],
                operations: Any, resource_pool: Any, context: Any) -> Any:
        return self.scheduler.schedule_prepared(
            self.native_preparation, params=params, batch_order=batch_order,
            operations=operations, resource_pool=resource_pool, graph_ready_context=context,
            readiness_gate_enabled=bool(kwargs.get("readiness_gate_enabled", False)),
            decode_resume=kwargs.get("decode_resume"),
            decode_checkpoints=kwargs.get("decode_checkpoints"),
        )

    def _record(self, request: DecodeRequest) -> _RequestRecord:
        record = self._records.get(request)
        if record is None:
            record = _RequestRecord(len(self._by_id) + 1, request)
            self._records[request] = record
            self._by_id[record.request_id] = record
        return record

    def _receipt(self, record: _RequestRecord, kind: str, *, verified: bool, calls: int,
                 elapsed_ms: float, reason: Optional[str] = None) -> Dict[str, Any]:
        return {
            "request_id": record.request_id, "execution_kind": kind, "verified": verified,
            "actual_decoder_calls": calls, "original_decode_ms": record.original_decode_ms,
            "current_elapsed_ms": elapsed_ms, "source_runtime_ms": record.source_runtime_ms,
            "source_initial_decode_runtime_ms": record.source_initial_decode_runtime_ms, "reason": reason,
        }

    def _event(self, record: _RequestRecord, receipt: Dict[str, Any], *, objective_name: str) -> None:
        if self.event_sink is not None:
            event_type = receipt["execution_kind"]
            if receipt["actual_decoder_calls"] and receipt["reason"] is not None:
                event_type = "decoder_failed"
            event = dict(receipt, event_type=event_type, search_objective=objective_name,
                         dispatch_mode=record.request.dispatch_mode, dispatch_rule=record.request.dispatch_rule,
                         elapsed_ms=max(int((self.clock() - self.started_at) * 1000), 0))
            event_id = self.event_sink(event)
            if event_id is not None:
                receipt["source_event_ref"] = event_id

    def _skip(self, record: _RequestRecord, *, reason: str, objective_name: str, started: float,
              error: Optional[SharedSearchSkip] = None) -> None:
        self.skipped_requests += 1
        receipt = self._receipt(record, "decode_skipped", verified=False, calls=0,
                                elapsed_ms=max((self.clock() - started) * 1000, 0), reason=reason)
        self._event(record, receipt, objective_name=objective_name)
        if error is None:
            error = SharedSearchSkip(reason, request_id=record.request_id, receipt=receipt)
        else:
            error.request_id, error.receipt = record.request_id, receipt
        raise error

    def evaluate(self, *, objective_name: str, optimizer_algo_stats: Optional[Dict[str, Any]],
                 before_decode: Optional[Callable[[], None]], redecode_reason: Optional[str],
                 schedule_kwargs: Dict[str, Any]) -> DecodedEvaluation:
        started = self.clock()
        request, params, batch_order, operations, pool, context = self._request(schedule_kwargs)
        record = self._record(request)
        if redecode_reason is not None and redecode_reason not in _REDECODE_KINDS:
            raise ValueError("Unknown shared decode reconstruction reason: " + str(redecode_reason))
        resumed = schedule_kwargs.get("decode_resume") is not None
        needs_capture = (redecode_reason == "capture_checkpoints"
                         or (not resumed and schedule_kwargs.get("decode_checkpoints") is not None))
        if record.verified and record.entry_id is not None and not needs_capture:
            if record.entry_id in self.archive:
                candidate = self.archive.view(record.entry_id, objective=objective_name)
                summary = candidate["summary"]
                source_prefix = self._by_id[candidate["decode_receipt"]["request_id"]].request.parameter_warnings
                if request.parameter_warnings != source_prefix:
                    # Content coalescing keeps the archive's first evidence. Parameter diagnostics
                    # belong to this request; replace only that native warning prefix on the owned copy.
                    summary = copy(summary)
                    summary.warnings = list(request.parameter_warnings) + list(summary.warnings[len(source_prefix):])
                self.reused_decisions += 1
                receipt = self._receipt(record, "decision_reused", verified=True, calls=0,
                                        elapsed_ms=max((self.clock() - started) * 1000, 0))
                self._event(record, receipt, objective_name=objective_name)
                return DecodedEvaluation(candidate["results"], summary, candidate["metrics"],
                                         params.strategy, dict(params.used_params), candidate["algo_stats"], receipt,
                                         record.entry_id, ArchiveObservation(entry_id=record.entry_id, reused=True))
            if redecode_reason != "restore_parent":
                self._skip(record, reason="seen_without_payload", objective_name=objective_name, started=started)
        kind = _REDECODE_KINDS.get(redecode_reason) if redecode_reason else None
        if kind is None:
            kind = "trial_decode" if resumed else ("capture_checkpoints" if record.verified else "new_decision")
        cost_kind = "sgs_resume" if resumed else ("sgs_full" if request.dispatch_mode == "sgs" else "batch_order_full")
        unpruned_sgs = cost_kind == "sgs_full" and not request.score_enabled
        try:
            self.budget.require_decode(cost_kind, reserve_full=resumed,
                                       first_construction=self.actual_decoder_calls == 0,
                                       unpruned_sgs=unpruned_sgs)
        except SharedSearchSkip as exc:
            self._skip(record, reason=exc.reason, objective_name=objective_name, started=started, error=exc)
        if before_decode is not None:
            before_decode()
        call_started = self.clock()
        if call_started >= self.deadline:
            try:
                self.budget.reject("time_budget")
            except SharedSearchSkip as exc:
                self._skip(record, reason=exc.reason, objective_name=objective_name, started=started, error=exc)
        self.actual_decoder_calls += 1
        self._execution_counts[kind] = self._execution_counts.get(kind, 0) + 1
        try:
            res, summ, used_strategy, used_params = self._decode(schedule_kwargs, params, batch_order,
                                                               operations, pool, context)
            metrics = compute_metrics(res, self.batches, expected_operations=self.operations,
                                      seed_results=self.seed_results,
                                      failure_details=summ.failure_details,
                                      prepared=self.evaluation_context)
            algo_stats = merge_algo_stats(optimizer_algo_stats, self.scheduler.last_algo_stats)
        except Exception as exc:
            elapsed = max(self.clock() - call_started, 0)
            self.budget.record_decode(cost_kind, elapsed, unpruned_sgs=unpruned_sgs)
            self.failed_decoder_calls += 1
            receipt = self._receipt(record, kind, verified=False, calls=1, elapsed_ms=elapsed * 1000,
                                    reason=type(exc).__name__)
            self._event(record, receipt, objective_name=objective_name)
            raise
        elapsed = max(self.clock() - call_started, 0)
        self.budget.record_decode(cost_kind, elapsed, unpruned_sgs=unpruned_sgs)
        if record.original_decode_ms is None:
            record.original_decode_ms = elapsed * 1000
        if kind in ("new_decision", "trial_decode"):
            record.exploration_requested = True
        receipt = self._receipt(record, kind, verified=not resumed, calls=1, elapsed_ms=elapsed * 1000)
        self._event(record, receipt, objective_name=objective_name)
        observation = self.archive.register_decode(
            {"results": res, "summary": summ, "metrics": metrics, "strategy": used_strategy,
             "params": used_params, "algo_stats": algo_stats, "decode_receipt": receipt},
            verified=not resumed, elapsed_ms=max(int((self.clock() - self.started_at) * 1000), 0),
        )
        entry_id = observation.entry_id
        receipt["entry_id"] = entry_id
        if entry_id in self.archive:
            if not resumed:
                if observation.reused:
                    archived_results = self.archive.results(entry_id)
                    if archived_results == res:
                        res = archived_results
                record.entry_id, record.verified = entry_id, True
        return DecodedEvaluation(res, summ, metrics, used_strategy, used_params, algo_stats, receipt,
                                 entry_id, observation)

    def bind_observation(self, receipt: Dict[str, Any], entry_id: Optional[int], verified: bool,
                         candidate: Dict[str, Any]) -> None:
        if entry_id is None or not verified or not receipt["verified"]:
            return
        record = self._by_id[receipt["request_id"]]
        record.entry_id, record.verified = entry_id, True
        new = record.exploration_requested and not record.new_decision_registered
        if new:
            record.new_decision_registered = True
            self.new_decisions += 1
        if record.source_runtime_ms is None:
            value = candidate.get("runtime_ms")
            record.source_runtime_ms = value if value is not None else record.original_decode_ms
            record.source_initial_decode_runtime_ms = candidate.get("initial_decode_runtime_ms")
        receipt.update(entry_id=entry_id, observation_bound=True, new_decision_registered=new,
                       source_runtime_ms=record.source_runtime_ms,
                       source_initial_decode_runtime_ms=record.source_initial_decode_runtime_ms)

    def record_local_reuse(self, *, execution_kind: str, objective_name: str,
                           request_id: Optional[int] = None, entry_id: Optional[int] = None) -> Dict[str, Any]:
        receipt = {"request_id": request_id, "entry_id": entry_id, "execution_kind": execution_kind,
                   "actual_decoder_calls": 0,
                   "verified": execution_kind == "reference_reused" and entry_id in self.archive,
                   "current_elapsed_ms": 0.0}
        if self.event_sink is not None:
            event_id = self.event_sink(dict(receipt, event_type="local_reuse", search_objective=objective_name,
                                            elapsed_ms=max(int((self.clock() - self.started_at) * 1000), 0)))
            if event_id is not None:
                receipt["source_event_ref"] = event_id
        return receipt

    def stats(self) -> Dict[str, Any]:
        return {"actual_decoder_calls": self.actual_decoder_calls, "new_decisions": self.new_decisions,
                "decision_reuses": self.reused_decisions, "skipped_requests": self.skipped_requests,
                "failed_decoder_calls": self.failed_decoder_calls, "request_count": len(self._records),
                "execution_counts": dict(self._execution_counts)}


def decode_and_metrics(
    *, decode_session: SharedDecodeSession, objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    before_decode: Optional[Callable[[], None]] = None, redecode_reason: Optional[str] = None,
    start_dt: datetime, strategy: Optional[SortStrategy] = None, strategy_params: Any = None, end_date: Any = None,
    batch_order_override: Any = None, dispatch_mode: Any = None, dispatch_rule: Any = None,
    readiness_gate_enabled: bool = False,
    graph_enabled: bool = False, graph_score_enabled: bool = False,
    graph_priority_key_by_op_id: Any = None, operation_resources: Any = None,
    resource_pair_rank: Any = None, decode_resume: Any = None, decode_checkpoints: Any = None,
) -> DecodedEvaluation:
    return decode_session.evaluate(
        objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats, before_decode=before_decode,
        redecode_reason=redecode_reason, schedule_kwargs={
            "strategy": strategy, "strategy_params": strategy_params,
            "start_dt": start_dt, "end_date": end_date,
            "batch_order_override": batch_order_override, "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule, "readiness_gate_enabled": readiness_gate_enabled,
            "graph_enabled": graph_enabled, "graph_score_enabled": graph_score_enabled,
            "graph_priority_key_by_op_id": graph_priority_key_by_op_id, "operation_resources": operation_resources,
            "resource_pair_rank": resource_pair_rank, "decode_resume": decode_resume,
            "decode_checkpoints": decode_checkpoints,
        },
    )


__all__ = ["DecodeRequest", "DecodedEvaluation", "SharedDecodeSession", "decode_and_metrics"]
