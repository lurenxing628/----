"""Repair accounting follows the actual portfolios admitted during cooperative rotation."""
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_repair import EliteRepairRun
from core.services.scheduler.run.optimizer_graph_ready_repair_accounting import RepairWorkAccounting
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import EliteRepairLimits, new_repair_report


def _elite(total, consumed=0):
    return {"neighborhood": SimpleNamespace(candidate_count=total), "decision_offset": consumed}


def test_late_basis_variants_pending_parents_and_top_k_exclusions_are_counted_once():
    first, pending, excluded = _elite(3, 1), _elite(4), _elite(7)
    report = {"repair_pruning_report": {"generated_candidates": 1}}
    pool = SimpleNamespace(limits=SimpleNamespace(enabled=True), report=report, elites=[pending],
                           parents_by_fingerprint={"first": first, "pending": pending, "excluded": excluded})
    accounting = RepairWorkAccounting()
    accounting.observe([first])
    # Profile search adds another basis to an already visited parent after its repair task yields.
    first["neighborhood"] = SimpleNamespace(candidate_count=5)
    accounting.observe([first])
    accounting.finish(pool)
    assert report["repair_pruning_report"]["candidate_space_total"] == 9
    assert report["repair_pruning_report"]["skipped_by_budget"] == 15
    assert report["selected_elites"] == 2
    assert report["skipped_elites_by_top_k"] == 1
    assert report["skipped_neighbors_by_top_k"] == 7
    assert report["repair_registered_portfolios"] == 2
    assert report["repair_visited_portfolios"] == 1


@pytest.mark.parametrize("total,consumed,generated", [(1, 2, 2), (2, 1, 2)])
def test_inconsistent_consumption_fails_instead_of_fabricating_remaining_work(total, consumed, generated):
    elite = _elite(total, consumed)
    pool = SimpleNamespace(limits=SimpleNamespace(enabled=True), elites=[elite], parents_by_fingerprint={"one": elite},
                           report={"repair_pruning_report": {"generated_candidates": generated}})
    accounting = RepairWorkAccounting()
    with pytest.raises(ValueError, match="repair"):
        accounting.finish(pool)


def test_exhausted_stage_accepts_new_work_without_resetting_round_or_decode_caps():
    elite = _elite(2, 2)
    limits = EliteRepairLimits()
    pool = SimpleNamespace(limits=limits, elites=[elite], report=new_repair_report(limits, objective_name="min_overdue"))
    budget = SimpleNamespace(remaining_candidates=lambda: 2)
    run = EliteRepairRun(pool, state=SimpleNamespace(best=None), evaluate=None, budget=budget, deadline=1.0,
                         clock=lambda: 0.0, t_begin=0.0, attempts=[], improvement_trace=[], report_state=None, strict_mode=True)
    run.exhausted = True
    run.report["repair_rounds_completed"] = 1
    assert not run.available()
    elite["neighborhood"] = SimpleNamespace(candidate_count=3)
    assert run.available()
    run.report["repair_rounds_completed"] = limits.max_rounds
    assert not run.available()
    run.report["repair_rounds_completed"] = 1
    budget.remaining_candidates = lambda: 0
    assert not run.available()
    budget.remaining_candidates = lambda: 2
    run.clock = lambda: 1.0
    assert not run.available()
