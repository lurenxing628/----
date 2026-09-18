"""Conservative hints protect complete qualification loss, not partial loss."""
import hashlib
import json
from types import SimpleNamespace

from core.algorithm_runtime.resource_demand import ResourceDemand
from core.algorithms import GreedyScheduler, SortStrategy
from tests._support.optimizer_end_to_end_cases import case_environment, fixture_data
from tests._support.optimizer_end_to_end_schedule import schedule_payload


def _operation(op_id, op_type, **fields):
    values = dict(id=op_id, batch_id="B" + str(op_id), piece_id=None, source="internal",
                  machine_id="", operator_id="", op_type_id=op_type)
    values.update(fields)
    return SimpleNamespace(**values)


def _pool():
    return {"machines_by_op_type": {"F": ["M1", "M2", "M3"], "S": ["M1", "M2"]},
            "operators_by_machine": {"M1": ["O1", "O2"], "M2": ["O1"], "M3": ["O1", "O3"]},
            "machines_by_operator": {"O1": ["M1", "M2", "M3"]}}


def test_partial_operator_loss_leaves_an_alternative_and_keeps_a_zero_hint():
    pool = _pool()
    pool["machines_by_op_type"]["S"] = ["M1"]
    current, other = _operation(1, "F"), _operation(2, "S")
    demand = ResourceDemand([current, other], pool)
    # M1/O2 remains usable when another machine takes O1.
    assert demand.penalties(current, (("M3", "O1"), ("M3", "O3"))) == (0.0, 0.0)


def test_unique_machine_is_protected_even_with_multiple_qualified_operators():
    pool = _pool()
    pool["machines_by_op_type"]["S"] = ["M1"]
    current, other = _operation(1, "F"), _operation(2, "S")
    demand = ResourceDemand([current, other], pool)
    assert demand.penalties(current, (("M1", "O1"), ("M3", "O3"))) == (1.0, 0.0)


def test_unique_operator_is_protected_across_multiple_qualified_machines():
    current, other = _operation(1, "F"), _operation(2, "S", operator_id="O1")
    demand = ResourceDemand([current, other], _pool())
    assert demand.penalties(current, (("M3", "O1"), ("M3", "O3"))) == (1.0, 0.0)


def test_machine_operator_union_covering_every_pair_is_counted_once():
    current, other = _operation(1, "F"), _operation(2, "S")
    demand = ResourceDemand([current, other], _pool())
    # S has M1/O1, M1/O2, M2/O1: neither resource alone is mandatory,
    # but using M1 and O1 together removes every alternative.
    assert demand.penalties(current, (("M1", "O1"), ("M3", "O3"))) == (1.0, 0.0)


def test_same_pair_queries_exclude_their_own_head_and_retire_completed_claims():
    first = _operation(1, "F", machine_id="M1", operator_id="O1")
    second = _operation(2, "F", machine_id="M3", operator_id="O3")
    demand = ResourceDemand([first, second], _pool())
    assert demand.penalty(first, "M1", "O1") == 0.0
    assert demand.penalty(second, "M1", "O1") == 1.0
    demand.complete(1)
    assert demand.penalty(second, "M1", "O1") == 0.0


def test_shift_pool_baseline_restores_the_complete_historical_schedule_and_vectors():
    # Source afc0551 historical end-to-end acceptance, shift_pool baseline.
    # This fingerprint checks all rows/resources/times, not only a relaxed score.
    # 2026-09-18 revision (decision dispatch-rule-working-hour-slack-and-priority-weight): the slack key
    # now scales by priority weight, so critical/urgent batches go first. Same 12 overdue batches,
    # weighted tardiness 3136.5 -> 2972.5 and makespan 288.5 -> 268.0, plain tardiness 1489.5 -> 1544.0.
    # The working-hour span alone (item 10) reproduces the afc0551 fingerprint 7c8ba505... on this fixture.
    with case_environment(fixture_data("shift_pool"), "min_overdue", {"seed": 0, "time_budget_seconds": 1}) as env:
        scheduler = GreedyScheduler(env.cal_svc, env.cfg)
        results, summary, *_ = scheduler.schedule(
            env.algo_ops_to_schedule, env.batches, strategy=SortStrategy.FIFO,
            start_dt=env.start_dt_norm, machine_downtimes=env.downtime_map, resource_pool=env.resource_pool,
            seed_results=[], dispatch_mode="sgs", dispatch_rule="slack", strict_mode=True,
        )
        payload = schedule_payload(SimpleNamespace(results=results, summary=summary), env)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert fingerprint == "c2936a9539d52ad93554c22b7c9858ca2297204ee06c880e4cc19c709e3ad58f"
    assert payload["quality_vectors"] == {
        "min_overdue": [0.0, 12.0, 2972.5, 1544.0, 268.0, 0.0],
        "min_tardiness": [0.0, 1544.0, 12.0, 2972.5, 268.0, 0.0],
        "min_weighted_tardiness": [0.0, 2972.5, 1544.0, 268.0, 0.0],
        "min_changeover": [0.0, 0.0, 12.0, 1544.0, 2972.5, 268.0],
    }
