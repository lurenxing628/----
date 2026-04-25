from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class OptimizerRuntime:
    scheduler_factory: Callable[..., Any]
    clock: Callable[[], float]
    rng_factory: Callable[[int], Any]
    run_ortools_warmstart: Callable[..., Optional[dict]]
    run_multi_start: Callable[..., Optional[dict]]
    run_local_search: Callable[..., Optional[dict]]
