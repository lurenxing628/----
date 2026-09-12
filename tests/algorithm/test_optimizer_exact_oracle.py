"""Small independent exact schedules anchor full objective-vector quality claims."""
from dataclasses import replace

import pytest

from tests._support.optimizer_exact_oracle import (
    OBJECTIVES,
    SCOPE,
    ScheduledOperation,
    TinyCase,
    TinyOperation,
    compare_to_exact,
    improving_case,
    score_schedule,
    solve_exact,
    tie_chain_case,
)

EXPECTED_BEST = {
    "min_overdue": (0, 1, 6, 6, 36, 2),
    "min_tardiness": (0, 6, 1, 6, 36, 2),
    "min_weighted_tardiness": (0, 6, 6, 36, 2),
    "min_changeover": (0, 1, 1, 12, 12, 36),
}
EXPECTED_INPUT = {
    "min_overdue": (0, 2, 18, 6, 36, 3),
    "min_tardiness": (0, 6, 2, 18, 36, 3),
    "min_weighted_tardiness": (0, 18, 6, 36, 3),
    "min_changeover": (0, 3, 2, 6, 18, 36),
}


def _input_order_schedule(case):
    clock, rows = 0, []
    for op in case.operations:
        rows.append(ScheduledOperation(op.op_id, clock, clock + op.duration_minutes))
        clock += op.duration_minutes
    return tuple(rows)


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_four_independent_batches_have_explicit_improving_optima(objective):
    case = improving_case()
    exact = solve_exact(case, objective)
    assert exact.topological_orders == 24
    assert exact.best_score == EXPECTED_BEST[objective]
    assert exact.applicability == SCOPE
    assert score_schedule(case, _input_order_schedule(case), objective) == EXPECTED_INPUT[objective]
    assert exact.best_score < EXPECTED_INPUT[objective]
    assert exact.schedules
    assert all(score_schedule(case, schedule, objective) == exact.best_score for schedule in exact.schedules)


@pytest.mark.parametrize("objective", OBJECTIVES)
def test_chain_is_a_legal_no_improvement_case(objective):
    case = tie_chain_case()
    exact = solve_exact(case, objective)
    assert exact.topological_orders == len(exact.schedules) == 1
    assert exact.schedules[0] == _input_order_schedule(case)
    expected = (0, 0, 0, 24, 0) if objective == "min_weighted_tardiness" else (
        (0, 0, 0, 0, 0, 24) if objective == "min_changeover" else (0, 0, 0, 0, 24, 0))
    assert exact.best_score == expected
    report = compare_to_exact(case, exact.schedules[0], objective)
    assert report["is_optimal"] is True
    assert report["first_differing_metric"] is None


def test_gap_is_lexicographic_and_later_components_may_be_better():
    case = improving_case()
    report = compare_to_exact(case, _input_order_schedule(case), "min_changeover")
    assert report["is_optimal"] is False
    assert report["first_differing_metric"] == "changeover_count"
    assert report["gap_vector"] == (0, 2, 1, -6, 6, 0)
    assert report["scope"] == SCOPE


def test_due_exclusive_equality_counts_overdue_with_zero_tardiness():
    case = TinyCase("due_boundary", (TinyOperation(1, "A", 1440),), {"A": 1440}, {"A": "critical"})
    assert solve_exact(case, "min_overdue").best_score == (0, 1, 0, 0, 24, 0)
    delayed = (ScheduledOperation(1, 60, 1500),)
    assert score_schedule(case, delayed, "min_overdue") == (0, 1, 3, 1, 24, 0)


def test_six_operations_with_dag_precedence_are_enumerated_once_per_order():
    case = TinyCase("six", tuple(TinyOperation(index, "B", 1, predecessors=(1,) if index > 1 else ())
                                for index in range(1, 7)), {"B": 1440}, {"B": "normal"})
    exact = solve_exact(case, "min_overdue")
    assert exact.topological_orders == len(exact.schedules) == 120
    assert exact.best_score == (0, 0, 0, 0, 0.1, 0)


@pytest.mark.parametrize("change, message", [
    ({"duration_minutes": 0}, "duration"), ({"duration_minutes": 1.5}, "duration"),
    ({"release_minute": 1}, "zero release"), ({"release_minute": True}, "release"),
    ({"machine_id": "M1"}, "fixed machine"), ({"operator_id": "O1"}, "fixed machine"),
    ({"predecessors": (99,)}, "unknown predecessor"), ({"predecessors": (1,)}, "cyclic"),
    ({"predecessors": (2, 2)}, "duplicate predecessor"), ({"family": ""}, "family"),
])
def test_out_of_domain_inputs_are_rejected(change, message):
    case = improving_case()
    case = replace(case, operations=(replace(case.operations[0], **change),) + case.operations[1:])
    with pytest.raises(ValueError, match=message):
        solve_exact(case, "min_overdue")


@pytest.mark.parametrize("change, message", [
    ({"operations": ()}, "one to six"),
    ({"due_minute_by_batch": {"A": 1440}}, "cover exactly"),
    ({"priority_by_batch": {"A": "high", "B": "urgent", "C": "critical", "D": "normal"}}, "unknown priority"),
])
def test_case_shape_is_not_silently_repaired(change, message):
    with pytest.raises(ValueError, match=message):
        solve_exact(replace(improving_case(), **change), "min_overdue")


def test_duplicate_ids_excessive_size_and_invalid_due_are_rejected():
    case = improving_case()
    for changed, message in (
        (replace(case, operations=case.operations + (case.operations[0],)), "duplicate operation"),
        (replace(case, operations=case.operations * 2), "one to six"),
        (replace(case, due_minute_by_batch=dict(case.due_minute_by_batch, A=1.5)), "due boundary"),
    ):
        with pytest.raises(ValueError, match=message):
            solve_exact(changed, "min_overdue")


@pytest.mark.parametrize("schedule, message", [
    ((ScheduledOperation(1, 0, 360),), "exactly once"),
    (tuple(ScheduledOperation(1, index * 360, (index + 1) * 360) for index in range(4)), "exactly once"),
    ((ScheduledOperation(1, 0, 361), ScheduledOperation(2, 361, 721),
      ScheduledOperation(3, 721, 1081), ScheduledOperation(4, 1081, 1441)), "duration"),
    ((ScheduledOperation(2, 0, 360), ScheduledOperation(1, 360, 720),
      ScheduledOperation(3, 720, 1080), ScheduledOperation(4, 1080, 1440)), "precedence"),
])
def test_schedule_identity_duration_and_precedence_are_audited(schedule, message):
    with pytest.raises(ValueError, match=message):
        score_schedule(tie_chain_case(), schedule, "min_overdue")


def test_resource_overlap_and_invalid_objectives_are_rejected():
    case = improving_case()
    overlap = tuple(ScheduledOperation(op.op_id, 0, op.duration_minutes) for op in case.operations)
    with pytest.raises(ValueError, match="resource overlap"):
        score_schedule(case, overlap, "min_overdue")
    for action in (lambda: solve_exact(case, "unknown"),
                   lambda: score_schedule(case, _input_order_schedule(case), "unknown")):
        with pytest.raises(ValueError, match="unknown objective"):
            action()


def test_actual_resource_assignment_must_match_fixed_eligibility():
    case = improving_case()
    schedule = _input_order_schedule(case)
    for changed in (replace(schedule[0], machine_id="OTHER"), replace(schedule[0], operator_id="OTHER")):
        with pytest.raises(ValueError, match="fixed resource eligibility"):
            score_schedule(case, (changed,) + schedule[1:], "min_overdue")
    remapped = replace(case, operations=tuple(replace(op, machine_id="M9", operator_id="O9") for op in case.operations))
    exact = solve_exact(remapped, "min_overdue")
    assert score_schedule(remapped, exact.schedules[0], "min_overdue") == EXPECTED_BEST["min_overdue"]
