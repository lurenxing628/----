"""SGS ready-time ownership requires the explicit complete-piece graph contract."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.dispatch_rules import DispatchRule
from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.piece_input import operation_dispatch_state
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy.dispatch import sgs


@pytest.mark.parametrize("piece", [None, "legacy-piece-label"])
@pytest.mark.parametrize("context,has_graph,enabled", [
    ({}, True, False),
    ({"piece_scope": False}, True, False),
    ({"piece_scope": True}, True, True),
    ({"piece_scope": True}, False, False),
    (None, True, False),
])
def test_seed_end_times_require_explicit_piece_scope(monkeypatch, piece, context, has_graph, enabled):
    graph = {} if has_graph else None
    seed_end = datetime(2026, 9, 9, 10)
    state = ScheduleRunState(base_time=seed_end,
                             results=[ScheduleResult(10, "OP10", "B1", 10, end_time=seed_end)])
    operations = {"B1": [SimpleNamespace(id=20, piece_id=piece)]}
    monkeypatch.setattr(sgs, "_prepare_graph_ready_state", lambda *_args, **_kwargs: graph)
    monkeypatch.setattr(sgs, "_collect_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(sgs, "_ensure_graph_ready_complete", lambda **_kwargs: None)
    sgs._run_sgs_loop(None, state, operations, ["B1"], {}, {}, {}, DispatchRule.SLACK, None, None,
                      False, None, False, 1.0, {}, context)
    if enabled:
        assert graph is not None
        assert graph["end_time_by_op_id"] == {10: seed_end}
    elif graph is not None:
        assert "end_time_by_op_id" not in graph
    assert state.results[0].end_time == seed_end


@pytest.mark.parametrize("ready_check", [False, True])
@pytest.mark.parametrize("checkpoint", [False, True])
def test_piece_dispatch_and_checkpoint_keep_readiness_policy_and_predecessors(ready_check, checkpoint):
    state = ScheduleRunState(base_time=datetime(2026, 9, 9), readiness_gate_enabled=ready_check)
    state.batch_progress["B1"] = datetime(2026, 9, 20)
    if checkpoint:
        state = state.clone()
    graph = {"end_time_by_op_id": {1: datetime(2026, 9, 10)}, "predecessor_op_ids_by_op_id": {2: {1}}}
    op = SimpleNamespace(id=2, batch_id="B1")
    batch = SimpleNamespace(ready_date="2026-09-15")
    dispatched = operation_dispatch_state(state, graph, op, batch)
    assert dispatched.prev_end("B1") == datetime(2026, 9, 15 if ready_check else 10)
    assert state.prev_end("B1") == datetime(2026, 9, 20)
