from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_candidate_specs import (
    CANDIDATE_KIND_BASELINE,
    CANDIDATE_KIND_CRITICAL_CHAIN,
    generate_candidate_specs,
)


def test_candidate_generation_defaults_to_baseline_plus_five_stable_graph_candidates() -> None:
    specs = generate_candidate_specs()

    assert [spec.candidate_key for spec in specs] == [
        "baseline",
        "graph_w1_of_5",
        "graph_w2_of_5",
        "graph_w3_of_5",
        "graph_w4_of_5",
        "graph_w5_of_5",
    ]
    assert specs[0].kind == CANDIDATE_KIND_BASELINE
    assert specs[0].graph_enabled is False
    assert specs[0].graph_critical_weight == 0
    assert specs[0].graph_impact_weight == 0
    assert [spec.kind for spec in specs[1:]] == [CANDIDATE_KIND_CRITICAL_CHAIN] * 5
    assert [spec.graph_critical_weight for spec in specs[1:]] == [250, 375, 500, 625, 750]
    assert [spec.graph_impact_weight for spec in specs[1:]] == [5, 8, 10, 12, 15]


@pytest.mark.parametrize(
    ("weight_count", "keys"),
    [
        (3, ["baseline", "graph_w1_of_3", "graph_w2_of_3", "graph_w3_of_3"]),
        (
            7,
            [
                "baseline",
                "graph_w1_of_7",
                "graph_w2_of_7",
                "graph_w3_of_7",
                "graph_w4_of_7",
                "graph_w5_of_7",
                "graph_w6_of_7",
                "graph_w7_of_7",
            ],
        ),
    ],
)
def test_candidate_generation_supports_only_planned_weight_counts(weight_count: int, keys: list) -> None:
    specs = generate_candidate_specs(weight_count=weight_count, base_critical_weight=100, base_impact_weight=20)

    assert [spec.candidate_key for spec in specs] == keys
    assert specs[0].sequence == 0
    assert [spec.sequence for spec in specs] == list(range(len(specs)))


def test_candidate_generation_rejects_unplanned_weight_count() -> None:
    with pytest.raises(ValidationError) as exc_info:
        generate_candidate_specs(weight_count=4)

    assert exc_info.value.field == "candidate_weight_count"


def test_candidate_generation_rejects_bool_or_negative_base_weights() -> None:
    with pytest.raises(ValidationError):
        generate_candidate_specs(base_critical_weight=True)
    with pytest.raises(ValidationError):
        generate_candidate_specs(base_impact_weight=-1)
