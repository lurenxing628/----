from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.services.scheduler.run.schedule_orchestrator import _normalize_optimizer_outcome


def test_orchestrator_rejects_bare_duck_typed_optimizer_outcome() -> None:
    with pytest.raises(TypeError):
        _normalize_optimizer_outcome(
            SimpleNamespace(
                results=[],
                summary=None,
                used_strategy=None,
                used_params={},
                metrics=None,
                best_score=(),
                best_order=[],
                attempts=[],
                improvement_trace=[],
                algo_mode="greedy",
                objective_name="min_overdue",
                time_budget_seconds=1,
                algo_stats={},
            )
        )
