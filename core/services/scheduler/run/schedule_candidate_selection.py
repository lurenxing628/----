"""Persist the business objective winners found by the shared search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .optimizer.shared_process import numeric_score


@dataclass(frozen=True)
class BusinessObjectiveSelectionResult:
    selected_candidate_key: str
    selected_plan: Any
    primary_objective: str
    target_objectives: Tuple[str, ...]
    objective_winners: Dict[str, Optional[str]]
    objective_winner_reasons: Dict[str, Optional[str]]
    objective_field_order: Dict[str, List[str]]
    selected_score: Tuple[float, ...]
    scoring_scope: Dict[str, Any]
    reason_code: str
    evidence_state: str

    def to_dict(self) -> Dict[str, Any]:
        return {"primary_objective": self.primary_objective,
                "target_objectives": list(self.target_objectives),
                "selected_candidate_key": self.selected_candidate_key,
                "objective_winners": dict(self.objective_winners),
                "objective_winner_reasons": dict(self.objective_winner_reasons),
                "objective_field_order": dict(self.objective_field_order),
                "selected_score": numeric_score(self.selected_score,
                    components_known=self.scoring_scope["components_known"]),
                "reason_code": self.reason_code, "scoring_scope": self.scoring_scope,
                "evidence_state": self.evidence_state}



__all__ = ["BusinessObjectiveSelectionResult"]
