"""Production multi-start hooks preserve outcomes while skipping proven work."""

import pytest

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.services.scheduler.run import optimizer_multi_start as multi
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests.algorithm.test_optimizer_multi_start_decision_dedup import _fingerprint, _inputs, _order

# Four sort strategies times the SGS rule pool: registry rules plus the ATC k ladder. The graph
# fixture carries no graph score (``score_enabled`` absent), so the decoder ignores its keys and
# the rule decides every pick: the whole pool is worth a start there too. Rule scoping by graph
# key ties is covered in test_optimizer_graph_rule_scope_contract.py.
KEYS = ["priority_first", "due_date_first", "weighted", "fifo"]
REGISTRY = ["slack", "cr", "atc"]


def _pool_size(graph):
    return len(dispatch_rule_search_pool(REGISTRY))


def _run(inputs, *, build_order=None, clock=lambda: 0.0, deadline=5.0, phase_deadline=None):
    attempts = []
    state = OptimizationSearchReportState("test", 0, 5, "min_overdue", 0.0)
    best = multi._run_multi_start(
        keys=list(KEYS), dispatch_modes=["sgs"],
        dispatch_rule_cfg="slack", valid_dispatch_rules=["slack", "cr", "atc"],
        scheduler=inputs["scheduler"], algo_ops_to_schedule=inputs["operations"], batches=inputs["batches"],
        start_dt=inputs["start_dt"], end_date=None, downtime_map={}, seed_sr_list=[],
        cfg=inputs["scheduler"].config, resource_pool=None, objective_name="min_overdue",
        deadline=deadline, phase_deadline=phase_deadline, attempts=attempts, improvement_trace=[],
        best=None, t_begin=0.0, build_order=build_order or (lambda strategy, params: _order(inputs, strategy, params)),
        strict_mode=True, graph_ready_context=inputs["graph_ready_context"], clock=clock,
        search_report_state=state,
    )
    return best, state, attempts


@pytest.mark.parametrize("graph", [False, True])
def test_real_multi_start_reduces_decodes_without_fake_fingerprint_evaluations(schema_conn, monkeypatch, graph):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn, graph=graph)
    optimized, state, attempts = _run(inputs)
    assert optimized is not None and optimized["summary"].failed_ops == 0
    assert state.candidate_profile is not None
    efficiency = state.candidate_profile["multi_start_efficiency"]
    pool, configured = _pool_size(graph), len(KEYS) * _pool_size(graph)
    assert efficiency["configured_candidates"] == configured
    assert efficiency["eligible_candidates"] == configured
    # Every strategy builds the same order here, so only one decode per rule token survives dedup;
    # ladder tokens such as atc:k=16.0 are distinct decisions and must all decode.
    assert efficiency["decoded_candidates"] == state.evaluated_candidates == pool
    assert efficiency["predecode_pruned_candidates"] == configured - pool
    assert efficiency["skipped_by_budget"] == 0
    assert sum(row.get("candidate_status") == "pruned" for row in attempts) == configured - pool
    with monkeypatch.context() as uncached:
        uncached.setattr(multi.MultiStartDecisionCache, "has", lambda self, key: False)
        original, original_state, _attempts = _run(inputs)
    assert original_state.evaluated_candidates == configured
    assert original is not None
    assert original["score"] == optimized["score"]
    assert _fingerprint(original) == _fingerprint(optimized)


def test_order_construction_crossing_deadline_starts_no_decode(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    now = [0.0]

    def build(strategy, params):
        order = _order(inputs, strategy, params)
        now[0] = 5.0
        return order

    best, state, _attempts = _run(inputs, build_order=build, clock=lambda: now[0])
    assert best is None
    assert state.evaluated_candidates == 0
    assert state.deadline_reached
    assert state.candidate_profile is not None
    assert state.candidate_profile["multi_start_efficiency"]["skipped_by_budget"] == len(KEYS) * _pool_size(False)


def test_phase_slice_keeps_first_baseline_if_global_time_remains(schema_conn, monkeypatch):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    now = [1.0]
    original = multi._evaluate_multi_start_candidate

    def evaluate(**kwargs):
        candidate = original(**kwargs)
        now[0] += 0.5
        return candidate

    monkeypatch.setattr(multi, "_evaluate_multi_start_candidate", evaluate)
    best, state, _attempts = _run(inputs, clock=lambda: now[0], phase_deadline=0.5)
    assert best is not None and state.evaluated_candidates == 1
    assert not state.deadline_reached
    assert {"phase": "multi_start", "reason": "reserved_for_later_phases"} in state.skipped_phases
