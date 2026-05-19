from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.infrastructure.errors import ValidationError

CANDIDATE_KIND_BASELINE = "baseline"
CANDIDATE_KIND_CRITICAL_CHAIN = "critical_chain"

DEFAULT_CANDIDATE_WEIGHT_COUNT = 5
SUPPORTED_CANDIDATE_WEIGHT_COUNTS = (3, 5, 7)

_WEIGHT_MULTIPLIERS: Dict[int, Tuple[float, ...]] = {
    3: (0.50, 1.00, 1.50),
    5: (0.50, 0.75, 1.00, 1.25, 1.50),
    7: (0.40, 0.60, 0.80, 1.00, 1.20, 1.40, 1.60),
}


@dataclass(frozen=True)
class CandidateRunSpec:
    sequence: int
    candidate_key: str
    kind: str
    label: str
    graph_enabled: bool
    graph_critical_weight: int
    graph_impact_weight: int
    graph_downstream_weight: int
    multiplier: float


def _require_supported_weight_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("候选档数必须是整数。", field="candidate_weight_count")
    if value not in SUPPORTED_CANDIDATE_WEIGHT_COUNTS:
        supported = " / ".join(str(item) for item in SUPPORTED_CANDIDATE_WEIGHT_COUNTS)
        raise ValidationError(f"候选档数只支持 {supported}。", field="candidate_weight_count")
    return int(value)


def _require_non_negative_int(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} 必须是非负整数。", field=field)
    return int(value)


def generate_candidate_specs(
    *,
    weight_count: int = DEFAULT_CANDIDATE_WEIGHT_COUNT,
    base_critical_weight: int = 500,
    base_impact_weight: int = 10,
) -> List[CandidateRunSpec]:
    count = _require_supported_weight_count(weight_count)
    critical_base = _require_non_negative_int(base_critical_weight, field="base_critical_weight")
    impact_base = _require_non_negative_int(base_impact_weight, field="base_impact_weight")

    specs = [
        CandidateRunSpec(
            sequence=0,
            candidate_key="baseline",
            kind=CANDIDATE_KIND_BASELINE,
            label="原算法",
            graph_enabled=False,
            graph_critical_weight=0,
            graph_impact_weight=0,
            graph_downstream_weight=0,
            multiplier=0.0,
        )
    ]
    for index, multiplier in enumerate(_WEIGHT_MULTIPLIERS[count], start=1):
        specs.append(
            CandidateRunSpec(
                sequence=index,
                candidate_key=f"graph_w{index}_of_{count}",
                kind=CANDIDATE_KIND_CRITICAL_CHAIN,
                label=f"关键链候选 {index}/{count}",
                graph_enabled=True,
                graph_critical_weight=int(round(critical_base * float(multiplier))),
                graph_impact_weight=int(round(impact_base * float(multiplier))),
                graph_downstream_weight=max(1, int(round(1 * float(multiplier)))),
                multiplier=float(multiplier),
            )
        )
    return specs


__all__ = [
    "CANDIDATE_KIND_BASELINE",
    "CANDIDATE_KIND_CRITICAL_CHAIN",
    "CandidateRunSpec",
    "DEFAULT_CANDIDATE_WEIGHT_COUNT",
    "SUPPORTED_CANDIDATE_WEIGHT_COUNTS",
    "generate_candidate_specs",
]
