"""Shared multiprocessing helpers for optimizer benchmark scripts."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Iterable, List, Sequence, TypeVar

DEFAULT_BENCHMARK_WORKERS = 10

_T = TypeVar("_T")
_R = TypeVar("_R")


def positive_worker_count(raw_value: int, *, field: str = "--workers") -> int:
    workers = int(raw_value)
    if workers <= 0:
        raise SystemExit(f"{field} must be a positive integer")
    return workers


def parallel_map_ordered(func: Callable[[_T], _R], items: Iterable[_T], *, workers: int) -> List[_R]:
    tasks: Sequence[_T] = list(items)
    if not tasks:
        return []
    max_workers = min(positive_worker_count(workers), len(tasks))
    if max_workers <= 1:
        return [func(item) for item in tasks]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(func, tasks))
