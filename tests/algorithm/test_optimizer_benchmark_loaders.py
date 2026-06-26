"""Tests for vendored external benchmark loaders (SMTWT / JSP) + Moore-Hodgson."""

from __future__ import annotations

import pytest

from tests._support.optimizer_benchmark_loaders import (
    JSP_PROVEN_OPTIMUM,
    load_jsp_instance,
    load_rcpsp_instance,
    load_rcpsp_optima,
    load_smtwt_instances,
    load_smtwt_optima,
    moore_hodgson_min_tardy,
    rcpsp_critical_path_lower_bound,
)


def test_load_smtwt_wt40_has_125_well_formed_instances() -> None:
    instances = load_smtwt_instances(40)

    assert len(instances) == 125
    first = instances[0]
    assert first.num_jobs == 40
    assert len(first.processing_times) == 40
    assert len(first.weights) == 40
    assert len(first.due_dates) == 40
    # OR-Library: processing times in [1,100], weights in [1,10].
    assert all(p > 0 for p in first.processing_times)
    assert all(1 <= w <= 10 for w in first.weights)


def test_load_smtwt_optima_aligns_with_instances() -> None:
    optima = load_smtwt_optima(40)
    instances = load_smtwt_instances(40)

    assert len(optima) >= len(instances)
    assert all(value >= 0 for value in optima[: len(instances)])


def test_load_jsp_ft06_matches_known_shape_and_optimum() -> None:
    inst = load_jsp_instance("ft06")

    assert inst.num_jobs == 6
    assert inst.num_machines == 6
    assert all(len(job) == 6 for job in inst.jobs)
    # First op of job 1 in ft06 is (machine 2, duration 1).
    assert inst.jobs[0][0] == (2, 1)
    assert JSP_PROVEN_OPTIMUM["ft06"] == 55


def test_load_jsp_rejects_unknown_instance() -> None:
    with pytest.raises(FileNotFoundError):
        load_jsp_instance("does-not-exist")


@pytest.mark.parametrize(
    "processing_times, due_dates, expected_tardy",
    [
        ([1, 1, 1], [1, 2, 3], 0),  # all fit in EDD order
        ([5, 5], [1, 1], 2),  # each job alone already exceeds its due date
        ([1, 2, 3], [3, 3, 3], 1),  # keep the two short jobs on time, one late
    ],
)
def test_moore_hodgson_min_tardy_known_cases(
    processing_times, due_dates, expected_tardy
) -> None:
    assert moore_hodgson_min_tardy(processing_times, due_dates) == expected_tardy


def test_moore_hodgson_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        moore_hodgson_min_tardy([1, 2], [1])


def test_load_rcpsp_j301_1_matches_known_values() -> None:
    inst = load_rcpsp_instance("j301_1")

    assert inst.num_jobs == 32  # 30 real jobs + supersource + sink
    assert inst.durations[0] == 0  # supersource
    assert inst.durations[1] == 8  # job 2
    assert inst.durations[31] == 0  # sink
    assert inst.successors[0] == (2, 3, 4)  # job 1 -> {2,3,4}
    assert inst.demands[1] == (4, 0, 0, 0)  # job 2 requests 4 of R1
    assert inst.capacities == (12, 13, 4, 12)


def test_rcpsp_critical_path_lower_bound_never_exceeds_optimum() -> None:
    optima = load_rcpsp_optima()
    # j301_1 -> parameter 1, instance 1.
    assert optima[(1, 1)] == 43

    for name, key in [("j301_1", (1, 1)), ("j301_2", (1, 2)), ("j3013_5", (13, 5))]:
        inst = load_rcpsp_instance(name)
        lower_bound = rcpsp_critical_path_lower_bound(inst)
        assert 0 < lower_bound <= optima[key], f"{name}: CP-LB {lower_bound} > optimum {optima[key]}"


def test_load_rcpsp_optima_has_480_optima_records() -> None:
    optima = load_rcpsp_optima()
    # 480 published optimal makespans (48 parameters x 10 instances). Only a few
    # .sm instance files are vendored; this asserts the optima table size, not the
    # number of instance files present.
    assert len(optima) == 480
