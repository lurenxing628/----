"""One request ledger and real decode boundary for a shared optimizer run."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional, Tuple

from core.algorithm_contracts.ordering import build_normalized_batches_map, normalize_batch_order_override
from core.algorithms.evaluation import compute_metrics, prepare_evaluation_context
from core.algorithms.greedy.algo_stats import capture_algo_stats
from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.errors import ValidationError

from .shared_budget import SharedSearchSkip
from .signature_support import schedule_with_optional_strict_mode

_STATIC_GRAPH_FIELDS = (
    "enabled", "schedulable_op_ids", "fixed_op_ids", "fixed_op_sources_by_op_id",
    "predecessor_op_ids_by_op_id", "successor_op_ids_by_op_id", "sort_key_by_op_id", "piece_scope",
)
_RESOURCE_FIELDS = (
    "machines_by_op_type", "operators_by_machine", "machines_by_operator", "operator_skills", "pair_rank",
)
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
    strict_mode: bool
    readiness_gate_enabled: bool
    parameter_warnings: Tuple[str, ...]
    batch_order: Tuple[str, ...]
    sort_inputs: Tuple[Any, ...]
    static_graph: Tuple[Any, ...]
    score_enabled: bool
    graph_preorder: Tuple[Tuple[int, ...], ...]
    operation_resources: Tuple[Tuple[int, str, str], ...]
    resource_pool: Tuple[Any, ...]


@dataclass
class DecodedEvaluation:
    results: Any
    summary: Any
    metrics: Any
    used_strategy: Any
    used_params: Dict[str, Any]
    algo_stats: Dict[str, Any]
    receipt: Optional[Dict[str, Any]]


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


def _resource_signature(pool: Any) -> Tuple[Any, ...]:
    if pool is None:
        return ("none",)
    if not isinstance(pool, dict):
        raise ValidationError("共享解码资源池必须是映射。", field="resource_pool")
    return tuple((name, _immutable(pool[name])) for name in _RESOURCE_FIELDS if name in pool)


class SharedDecodeSession:
    """Keep request identity and costs; completed schedules belong to the archive."""

    def __init__(
        self, *, archive: Any, budget: Any, scheduler: Any, operations: Any, batches: Any,
        seed_results: Any, downtime_map: Any, resource_pool: Any,
        graph_ready_context: Optional[Dict[str, Any]] = None, clock: Callable[[], float],
        started_at: float, deadline: float, event_sink: Optional[Callable[[Dict[str, Any]], Optional[int]]] = None,
    ) -> None:
        from core.algorithms.greedy.scheduler import prepare_native_schedule_inputs

        self.archive, self.budget, self.scheduler = archive, budget, scheduler
        self.operations, self.batches, self.seed_results = operations, batches, seed_results
        self.downtime_map, self.resource_pool = downtime_map, resource_pool
        self._base_resource_signature = _resource_signature(resource_pool)
        self.clock, self.started_at, self.deadline = clock, started_at, deadline
        self.event_sink = event_sink
        self._normalized_batches = build_normalized_batches_map(batches)
        self.evaluation_context = prepare_evaluation_context(
            batches=batches, expected_operations=operations, seed_results=seed_results,
        )
        self.native_preparation = prepare_native_schedule_inputs(downtime_map, calendar=scheduler.calendar)
        self._graph_context = graph_ready_context
        self._static_graph = self._prepare_static_graph(graph_ready_context)
        self._operation_ids = frozenset(op.id for op in operations)
        self._records: Dict[DecodeRequest, _RequestRecord] = {}
        self._by_id: Dict[int, _RequestRecord] = {}
        self.actual_decoder_calls = 0
        self.new_decisions = 0
        self.reused_decisions = 0
        self.skipped_requests = 0
        self.failed_decoder_calls = 0
        self._execution_counts: Dict[str, int] = {}

    def _prepare_static_graph(self, context: Optional[Dict[str, Any]]) -> Tuple[Any, ...]:
        if context is None:
            return ("none",)
        from core.algorithms.greedy.dispatch.sgs_graph import prepare_graph_ready_topology

        # Native graph admission happens once for this run's owned, fixed topology.
        prepare_graph_ready_topology(context, self.operations)
        return ("piece" if context.get("piece_scope") else "linear",) + tuple(
            (name, _immutable(context[name])) for name in _STATIC_GRAPH_FIELDS if name in context
        )

    def _require_context(self, scheduler: Any, expected_operations: Any, kwargs: Dict[str, Any]) -> None:
        fixed = ((scheduler, self.scheduler), (expected_operations, self.operations),
                 (kwargs["batches"], self.batches), (kwargs.get("seed_results"), self.seed_results),
                 (kwargs.get("machine_downtimes"), self.downtime_map))
        if any(current is not original for current, original in fixed):
            raise ValueError("SharedDecodeSession requires the same scheduler and owned run inputs.")

    def _request(self, kwargs: Dict[str, Any]) -> Tuple[DecodeRequest, Any]:
        from core.algorithms.greedy.dispatch.sgs_graph import _graph_priority_key_map
        from core.algorithms.greedy.scheduler import _build_batch_order

        from .graph.predecode import graph_priority_preorder

        params = resolve_schedule_params(
            config=self.scheduler.config, strategy=kwargs.get("strategy"),
            strategy_params=kwargs.get("strategy_params"), start_dt=kwargs.get("start_dt"),
            end_date=kwargs.get("end_date"), dispatch_mode=kwargs.get("dispatch_mode"),
            dispatch_rule=kwargs.get("dispatch_rule"), resource_pool=kwargs.get("resource_pool"),
            strict_mode=bool(kwargs.get("strict_mode", False)),
        )
        strict, readiness = bool(kwargs.get("strict_mode", False)), bool(kwargs.get("readiness_gate_enabled", False))
        override = normalize_batch_order_override(kwargs.get("batch_order_override"), self._normalized_batches)
        full_override = bool(override) and len(override) == len(self._normalized_batches)
        batch_ranks = _build_batch_order(self._normalized_batches, params, batch_order_override=override,
                                       strict_mode=strict, readiness_gate_enabled=readiness)
        order = tuple(sorted(batch_ranks, key=batch_ranks.__getitem__))
        # The native sorting factory consumes only these weights. Source/profile labels do not dispatch.
        sort_inputs = () if full_override else (
            str(getattr(params.strategy, "value", params.strategy)),
            tuple((name, _immutable(params.used_params[name])) for name in ("priority_weight", "due_weight")
                  if name in params.used_params),
        )
        context = kwargs.get("graph_ready_context")
        score_enabled, preorder = False, ()
        static_graph = ("none",)
        if context is not None:
            if not isinstance(context, dict) or self._graph_context is None:
                raise ValueError("SharedDecodeSession requires its prepared graph input.")
            for name in _STATIC_GRAPH_FIELDS:
                current, original = context.get(name), self._graph_context.get(name)
                if current is not original and current != original:
                    raise ValueError("Static graph inputs changed within a SharedDecodeSession.")
            score_enabled = context.get("score_enabled", False)
            if not isinstance(score_enabled, bool):
                raise ValidationError("图评分开关 score_enabled 必须是 bool。", field="graph_ready_context")
            static_graph = self._static_graph
            if score_enabled:
                keys = context.get("graph_priority_key_by_op_id")
                if (not isinstance(keys, dict) or set(keys) != self._operation_ids
                        or any(type(op_id) is not int for op_id in keys)):
                    raise ValidationError("图评分 key 必须覆盖全部待排工序。", field="graph_ready_context")
                preorder = graph_priority_preorder(_graph_priority_key_map(keys, schedulable_ids=set(self._operation_ids)))
        resources = tuple(sorted((op.id, str(getattr(op, "machine_id", None) or "").strip(),
                                  str(getattr(op, "operator_id", None) or "").strip()) for op in kwargs["operations"]))
        pool = kwargs.get("resource_pool")
        pool_signature = self._base_resource_signature if pool is self.resource_pool else _resource_signature(pool)
        request = DecodeRequest(
            params.dispatch_mode_key, params.dispatch_rule_spec.token, params.base_time, params.end_dt_exclusive,
            params.auto_assign_enabled, strict, readiness, tuple(params.warnings), order, sort_inputs,
            static_graph, score_enabled, preorder, resources, pool_signature,
        )
        return request, params

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

    def evaluate(self, *, scheduler: Any, schedule_fn: Callable[..., Any], expected_operations: Any,
                 objective_name: str, optimizer_algo_stats: Optional[Dict[str, Any]],
                 before_decode: Optional[Callable[[], None]], redecode_reason: Optional[str],
                 schedule_kwargs: Dict[str, Any]) -> DecodedEvaluation:
        started = self.clock()
        self._require_context(scheduler, expected_operations, schedule_kwargs)
        request, params = self._request(schedule_kwargs)
        record = self._record(request)
        if redecode_reason is not None and redecode_reason not in _REDECODE_KINDS:
            raise ValueError("Unknown shared decode reconstruction reason: " + str(redecode_reason))
        resumed = schedule_kwargs.get("decode_resume") is not None
        needs_capture = (redecode_reason == "capture_checkpoints"
                         or (not resumed and schedule_kwargs.get("decode_checkpoints") is not None))
        if record.verified and record.entry_id is not None and not needs_capture:
            if record.entry_id in self.archive.retained_entry_ids:
                candidate = self.archive.materialize(record.entry_id, objective=objective_name)
                source_receipt = candidate.get("decode_receipt") or {}
                source_request_id: Optional[int] = source_receipt.get("request_id")
                source_record = self._by_id.get(source_request_id) if source_request_id is not None else None
                source_prefix = source_record.request.parameter_warnings if source_record is not None else ()
                # Content coalescing keeps the archive's first evidence. Parameter diagnostics
                # belong to this request; replace only that native warning prefix on the owned copy.
                candidate["summary"].warnings = (list(request.parameter_warnings)
                                                   + list(candidate["summary"].warnings[len(source_prefix):]))
                self.reused_decisions += 1
                receipt = self._receipt(record, "decision_reused", verified=True, calls=0,
                                        elapsed_ms=max((self.clock() - started) * 1000, 0))
                self._event(record, receipt, objective_name=objective_name)
                return DecodedEvaluation(candidate["results"], candidate["summary"], candidate["metrics"],
                                         params.strategy, dict(params.used_params), candidate.get("algo_stats") or {}, receipt)
            if redecode_reason != "restore_parent":
                self._skip(record, reason="seen_without_payload", objective_name=objective_name, started=started)
        kind = _REDECODE_KINDS.get(redecode_reason) if redecode_reason else None
        if kind is None:
            kind = "trial_decode" if resumed else ("capture_checkpoints" if record.verified else "new_decision")
        cost_kind = "sgs_resume" if resumed else ("sgs_full" if request.dispatch_mode == "sgs" else "batch_order_full")
        try:
            self.budget.require_decode(cost_kind, reserve_full=resumed, first_construction=self.actual_decoder_calls == 0)
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
            from core.algorithms.greedy.scheduler import GreedyScheduler

            native_kwargs = schedule_kwargs
            if (schedule_fn is schedule_with_optional_strict_mode
                    and getattr(scheduler.schedule, "__func__", None) is GreedyScheduler.schedule):
                native_kwargs = dict(schedule_kwargs, prepared_inputs=self.native_preparation)
            res, summ, used_strategy, used_params = schedule_fn(scheduler, **native_kwargs)
            metrics = compute_metrics(res, schedule_kwargs["batches"], expected_operations=expected_operations,
                                      seed_results=schedule_kwargs.get("seed_results"),
                                      failure_details=getattr(summ, "failure_details", ()),
                                      prepared=self.evaluation_context)
            algo_stats = capture_algo_stats(scheduler, optimizer_algo_stats)
        except Exception as exc:
            elapsed = max(self.clock() - call_started, 0)
            self.budget.record_decode(cost_kind, elapsed)
            self.failed_decoder_calls += 1
            receipt = self._receipt(record, kind, verified=False, calls=1, elapsed_ms=elapsed * 1000,
                                    reason=type(exc).__name__)
            self._event(record, receipt, objective_name=objective_name)
            raise
        elapsed = max(self.clock() - call_started, 0)
        self.budget.record_decode(cost_kind, elapsed)
        if record.original_decode_ms is None:
            record.original_decode_ms = elapsed * 1000
        if kind in ("new_decision", "trial_decode"):
            record.exploration_requested = True
        receipt = self._receipt(record, kind, verified=not resumed, calls=1, elapsed_ms=elapsed * 1000)
        self._event(record, receipt, objective_name=objective_name)
        return DecodedEvaluation(res, summ, metrics, used_strategy, used_params, algo_stats, receipt)

    def bind_observation(self, receipt: Optional[Dict[str, Any]], entry_id: Optional[int], verified: bool,
                         candidate: Optional[Dict[str, Any]] = None) -> None:
        if receipt is None or entry_id is None or not verified or not receipt.get("verified"):
            return
        record = self._by_id[receipt["request_id"]]
        record.entry_id, record.verified = entry_id, True
        new = record.exploration_requested and not record.new_decision_registered
        if new:
            record.new_decision_registered = True
            self.new_decisions += 1
        if record.source_runtime_ms is None:
            value = candidate.get("runtime_ms") if candidate is not None else None
            record.source_runtime_ms = value if value is not None else record.original_decode_ms
            record.source_initial_decode_runtime_ms = (candidate.get("initial_decode_runtime_ms")
                                                      if candidate is not None else None)
        receipt.update(entry_id=entry_id, observation_bound=True, new_decision_registered=new,
                       source_runtime_ms=record.source_runtime_ms,
                       source_initial_decode_runtime_ms=record.source_initial_decode_runtime_ms)

    def record_local_reuse(self, *, execution_kind: str, objective_name: str,
                           request_id: Optional[int] = None, entry_id: Optional[int] = None) -> Dict[str, Any]:
        receipt = {"request_id": request_id, "entry_id": entry_id, "execution_kind": execution_kind,
                   "actual_decoder_calls": 0,
                   "verified": execution_kind == "reference_reused" and entry_id in self.archive.retained_entry_ids,
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

    summary = stats


def decode_and_metrics(*, decode_session: SharedDecodeSession, scheduler: Any,
                       schedule_fn: Callable[..., Any], expected_operations: Any, objective_name: str,
                       optimizer_algo_stats: Optional[Dict[str, Any]] = None,
                       before_decode: Optional[Callable[[], None]] = None,
                       redecode_reason: Optional[str] = None, **schedule_kwargs: Any) -> DecodedEvaluation:
    return decode_session.evaluate(scheduler=scheduler, schedule_fn=schedule_fn,
                                   expected_operations=expected_operations, objective_name=objective_name,
                                   optimizer_algo_stats=optimizer_algo_stats, before_decode=before_decode,
                                   redecode_reason=redecode_reason, schedule_kwargs=schedule_kwargs)


__all__ = ["DecodeRequest", "DecodedEvaluation", "SharedDecodeSession", "decode_and_metrics"]
