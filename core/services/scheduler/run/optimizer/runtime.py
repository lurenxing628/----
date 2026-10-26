from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from core.algorithms.greedy.scheduler import GreedyScheduler

from .search_budget import SearchBudget


@dataclass(frozen=True)
class OptimizerRuntime:
    scheduler_factory: Callable[..., GreedyScheduler]
    clock: Callable[[], float]
    rng_factory: Callable[[int], Any]
    run_ortools_warmstart: Callable[..., Optional[dict]]


def _default_runtime() -> OptimizerRuntime:
    from ..schedule_optimizer_steps import run_ortools_warmstart

    return OptimizerRuntime(
        scheduler_factory=GreedyScheduler,
        clock=time.monotonic,
        rng_factory=random.Random,
        run_ortools_warmstart=run_ortools_warmstart,
    )


def resolve_runtime(runtime: Optional[OptimizerRuntime], search_budget: SearchBudget) -> OptimizerRuntime:
    """Resolve one runtime and bind its clock to the owned search budget."""
    return replace(runtime or _default_runtime(), clock=search_budget.clock)
