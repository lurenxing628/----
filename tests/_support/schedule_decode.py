"""Production decode entry for tests: one ``SharedDecodeSession`` request per call.

``config_snapshot`` builds the only accepted runtime configuration form
(``ScheduleConfigSnapshot``) from the registered defaults plus overrides of its fields.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.algorithm_contracts.resource_occupancy import ResourceOccupancy
from core.algorithm_contracts.resource_pool import DISABLED_RESOURCE_POOL, ResourcePool
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_runtime.operation_effort import internal_operation_effort
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics
from core.algorithms.evaluation_completion import prepare_evaluation_context
from core.models.batch import Batch
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot, snapshot_from_values
from core.services.scheduler.run.optimizer.config import resolve_optimizer_config, strategy_weights
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
from core.services.scheduler.run.optimizer.shared_decode import (
    DecodedEvaluation,
    SharedDecodeSession,
    decode_and_metrics,
)
from core.services.scheduler.run.schedule_shared_search import open_shared_search

# The scheduling window end a test without one decodes with: due_exclusive maps 9999-12-31 to "no limit".
NO_END_DATE = date(9999, 12, 31)


def config_snapshot(**overrides: Any) -> ScheduleConfigSnapshot:
    unknown = sorted(set(overrides) - {item.name for item in fields(ScheduleConfigSnapshot)})
    if unknown:
        raise TypeError(f"ScheduleConfigSnapshot 没有这些字段：{unknown}")
    values: Dict[str, Any] = default_snapshot_values()
    values.update(overrides)
    return snapshot_from_values(values)


def _clock() -> float:
    return 0.0


def unbounded_search_budget() -> SharedSearchBudget:
    """A run budget on the fixed test clock with no deadline, for a test that calls a budget-guarded graph
    helper (features, repair) directly instead of through an open shared search."""
    return SharedSearchBudget(clock=_clock, started_at=0.0, deadline=float("inf"),
                              target_objectives=("min_overdue",), configured_seconds=float("inf"))


def required_hours_by_op_id(operations: Sequence[OpForScheduleAlgo], batches: Mapping[str, Batch]) -> Dict[int, float]:
    """The run input's standard hours of the internal operations, by the production formula
    (``prepare_solver_input`` takes them from the same ``internal_operation_effort``)."""
    return {op.id: internal_operation_effort(op, batches[op.batch_id]).required_standard_hours
            for op in operations if op.source == "internal"}


def prepared_metrics(results: List[ScheduleResult], batches: Dict[str, Batch], *,
                     expected_operations: Iterable[OpForScheduleAlgo], failure_details: Iterable[Dict[str, Any]],
                     seed_occupancies_by_op_id: Mapping[int, Tuple[ResourceOccupancy, ...]],
                     seed_results: Iterable[ScheduleResult] = ()) -> ScheduleMetrics:
    """The metrics a run with these inputs gives ``results``: its evaluation facts are prepared from the inputs
    (``prepare_evaluation_context``), as the shared search prepares them once per run."""
    prepared = prepare_evaluation_context(batches=batches, expected_operations=expected_operations,
                                          seed_results=seed_results)
    return compute_metrics(results, prepared=prepared, failure_details=failure_details,
                           seed_occupancies_by_op_id=seed_occupancies_by_op_id)


def production_decode(scheduler: Any, **kwargs: Any) -> DecodedEvaluation:
    return production_decode_in_session(scheduler, **kwargs)[1]


def production_decode_in_session(scheduler: Any, *, operations: Any, batches: Any, start_dt: Any,
                                 end_date: date = NO_END_DATE, readiness_gate_enabled: bool = False,
                                 seed_results: Any = (), machine_downtimes: Any = None,
                                 resource_pool: ResourcePool = DISABLED_RESOURCE_POOL,
                                 graph_ready_context: Optional[Dict[str, Any]] = None, objective_name: str = "min_overdue",
                                 **decode_kwargs: Any) -> Tuple[SharedDecodeSession, DecodedEvaluation]:
    """Decode once through the shared optimizer's own search (``open_shared_search``), with a fixed clock and
    no deadline: ``SharedDecodeSession`` -> ``GreedyScheduler.schedule_prepared``.

    ``start_dt``, ``end_date`` (no scheduling window end by default) and ``readiness_gate_enabled`` are the run's,
    held by the session. A graph context passed here is the decode's graph input; its ``score_enabled`` and
    ``graph_priority_key_by_op_id`` become the request's graph switches unless given explicitly.
    The session is returned so tests can read the run's own preparation (e.g. its score cache).
    """
    session = open_shared_search(
        objective_name=objective_name, scheduler=scheduler, operations=operations, batches=batches,
        required_hours_by_op_id=required_hours_by_op_id(operations, batches), seed_results=list(seed_results),
        downtime_map={} if machine_downtimes is None else machine_downtimes, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context, start_dt=start_dt, end_date=end_date,
        readiness_gate_enabled=readiness_gate_enabled, clock=_clock, started_at=0.0, deadline=float("inf"),
        configured_seconds=float("inf"),
    ).decode_session
    if graph_ready_context is not None:
        decode_kwargs.setdefault("graph_enabled", True)
        decode_kwargs.setdefault("graph_score_enabled", graph_ready_context.get("score_enabled", False))
        decode_kwargs.setdefault("graph_priority_key_by_op_id",
                                 graph_ready_context.get("graph_priority_key_by_op_id"))
    return session, decode_in_session(session, objective_name=objective_name, **decode_kwargs)


def decode_in_session(session: SharedDecodeSession, *, objective_name: str = "min_overdue",
                      **decode_kwargs: Any) -> DecodedEvaluation:
    """One ``decode_and_metrics`` request in a test's session (the session holds the run's start and window).

    The decode choices a test leaves out are the scheduler configuration's, derived as the optimizer
    derives them (resolve_optimizer_config, strategy_weights); no batch order override, no graph switches and
    no pair-rank overrides.
    """
    config = session.scheduler.config
    optimizer = resolve_optimizer_config(config)
    strategy = decode_kwargs.setdefault("strategy", optimizer.strategy_enum)
    decode_kwargs.setdefault("strategy_params", strategy_weights(strategy, config))
    decode_kwargs.setdefault("dispatch_mode", optimizer.dispatch_mode)
    decode_kwargs.setdefault("dispatch_rule", optimizer.dispatch_rule)
    decode_kwargs.setdefault("batch_order_override", ())
    decode_kwargs.setdefault("graph_enabled", False)
    decode_kwargs.setdefault("graph_score_enabled", False)
    decode_kwargs.setdefault("graph_priority_key_by_op_id", None)
    decode_kwargs.setdefault("resource_pair_rank", {})
    return decode_and_metrics(decode_session=session, objective_name=objective_name, **decode_kwargs)


__all__ = ["NO_END_DATE", "config_snapshot", "decode_in_session", "prepared_metrics", "production_decode",
           "production_decode_in_session", "required_hours_by_op_id"]
