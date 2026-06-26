"""Tier-1 objective-comparable grading: greedy overdue_count vs exact optimum."""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from tests._support.optimizer_benchmark_grading import (
    build_jsp_folded_reference,
    grade_smtwt_overdue,
    smtwt_overdue_case,
)
from tests._support.optimizer_benchmark_loaders import load_smtwt_instances


def test_smtwt_overdue_case_is_single_resource_with_aligned_due_dates() -> None:
    instance = load_smtwt_instances(40)[0]
    case = smtwt_overdue_case(instance)

    assert len(case.operations) == instance.num_jobs
    assert len(case.batches) == instance.num_jobs
    assert {op.machine_id for op in case.operations} == {"machine-main"}
    assert {op.operator_id for op in case.operations} == {"operator-main"}
    # processing time p maps to p*24 hours (one day per unit).
    assert case.operations[0].duration_hours == float(instance.processing_times[0] * 24)


def test_greedy_never_beats_proven_overdue_optimum_on_wt40_sample() -> None:
    instances = load_smtwt_instances(40)[:8]

    graded = [grade_smtwt_overdue(inst) for inst in instances]

    for row in graded:
        # The proven-optimum invariant: greedy can equal but never beat the optimum.
        assert row["greedy_overdue_count"] >= row["optimal_overdue_count"]
        assert row["overdue_gap"] >= 0
        assert row["optimal_overdue_count"] >= 0


def test_grade_smtwt_overdue_reports_expected_fields() -> None:
    instance = load_smtwt_instances(40)[0]

    row = grade_smtwt_overdue(instance)

    assert set(row) == {
        "instance",
        "num_jobs",
        "greedy_overdue_count",
        "optimal_overdue_count",
        "overdue_gap",
        "is_optimal",
    }
    assert row["instance"] == instance.name
    assert row["num_jobs"] == 40


def test_jsp_folded_reference_is_proven_optimum_but_not_objective_comparable() -> None:
    # ft06 proven optimal makespan is 55; suppose APS folded run got 60.
    reference = build_jsp_folded_reference("ft06", actual_makespan_hours=60.0)

    assert reference["reference_type"] == "folded_not_comparable"
    assert reference["bound_is_objective_comparable"] is False
    assert reference["bound_metric"] == "makespan_hours"
    assert reference["best_known_upper_bound"] == 55.0
    assert reference["public"]["reference_label"] == "proven_optimum_makespan"
    # gap = (60 - 55) / 55 * 100
    assert reference["gap_to_best_known_pct"] == pytest.approx(9.0909, abs=1e-3)


def test_jsp_folded_reference_rejects_unknown_instance() -> None:
    with pytest.raises(ValidationError):
        build_jsp_folded_reference("nope", actual_makespan_hours=60.0)
