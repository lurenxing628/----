"""Production decode entry for tests: one ``SharedDecodeSession`` request per call.

``config_snapshot`` builds the only accepted runtime configuration form
(``ScheduleConfigSnapshot``) from the registered defaults plus overrides.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.algorithms.evaluation import prepare_evaluation_context
from core.models.objective import target_objectives_for
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot, snapshot_from_values
from core.services.scheduler.run.optimizer.shared_archive import SharedScheduleArchive
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget
from core.services.scheduler.run.optimizer.shared_decode import (
    DecodedEvaluation,
    SharedDecodeSession,
    decode_and_metrics,
)


def config_snapshot(**overrides: Any) -> ScheduleConfigSnapshot:
    values: Dict[str, Any] = default_snapshot_values()
    values.update(overrides)
    return snapshot_from_values(values)


def _clock() -> float:
    return 0.0


def production_session(scheduler: Any, *, operations: Any, batches: Any, start_dt: Any,
                       seed_results: Any = (), machine_downtimes: Any = None, resource_pool: Any = None,
                       graph_ready_context: Optional[Dict[str, Any]] = None,
                       objective_name: str = "min_overdue") -> SharedDecodeSession:
    """Build the production decode session exactly as the shared optimizer does."""
    seeds = list(seed_results)
    evaluation_context = prepare_evaluation_context(
        batches=batches, expected_operations=operations, seed_results=seeds,
    )
    targets = target_objectives_for(objective_name)
    archive = SharedScheduleArchive(objective_name, targets, evaluation_context.batch_by_op_id,
                                    set(batches) | set(evaluation_context.expected_by_batch))
    budget = SharedSearchBudget(clock=_clock, started_at=0.0, deadline=float("inf"),
                                target_objectives=targets, configured_seconds=float("inf"))
    return SharedDecodeSession(
        archive=archive, budget=budget, scheduler=scheduler, operations=operations, batches=batches,
        seed_results=seeds, downtime_map={} if machine_downtimes is None else machine_downtimes,
        resource_pool=resource_pool, graph_ready_context=graph_ready_context, clock=_clock,
        started_at=0.0, deadline=float("inf"), start_dt=start_dt, evaluation_context=evaluation_context,
    )


def production_decode(scheduler: Any, **kwargs: Any) -> DecodedEvaluation:
    return production_decode_in_session(scheduler, **kwargs)[1]


def production_decode_in_session(scheduler: Any, *, operations: Any, batches: Any, start_dt: Any,
                                 seed_results: Any = (), machine_downtimes: Any = None, resource_pool: Any = None,
                                 graph_ready_context: Optional[Dict[str, Any]] = None, objective_name: str = "min_overdue",
                                 **decode_kwargs: Any) -> Tuple[SharedDecodeSession, DecodedEvaluation]:
    """Decode once through ``SharedDecodeSession`` -> ``GreedyScheduler.schedule_prepared``.

    A graph context passed here is the decode's graph input; its ``score_enabled`` and
    ``graph_priority_key_by_op_id`` become the request's graph switches unless given explicitly.
    The session is returned so tests can read the run's own preparation (e.g. its score cache).
    """
    session = production_session(
        scheduler, operations=operations, batches=batches, start_dt=start_dt, seed_results=seed_results,
        machine_downtimes=machine_downtimes, resource_pool=resource_pool,
        graph_ready_context=graph_ready_context, objective_name=objective_name,
    )
    if graph_ready_context is not None:
        decode_kwargs.setdefault("graph_enabled", True)
        decode_kwargs.setdefault("graph_score_enabled", graph_ready_context.get("score_enabled", False))
        decode_kwargs.setdefault("graph_priority_key_by_op_id",
                                 graph_ready_context.get("graph_priority_key_by_op_id"))
    return session, decode_and_metrics(decode_session=session, objective_name=objective_name, **decode_kwargs)


__all__ = ["config_snapshot", "production_decode", "production_decode_in_session", "production_session"]
