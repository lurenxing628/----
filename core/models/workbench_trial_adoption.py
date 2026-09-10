"""Saved scenario adoption has its own identity, never a candidate alias."""

from dataclasses import dataclass
from typing import Any, Dict

from core.models.workbench_command import WorkbenchCommandRejected

ADOPT_ACTION = "trial.scenario.adopt"


class TrialAdoptionBlocked(WorkbenchCommandRejected):
    def __init__(self, code, message, issues=None):
        super().__init__(code, message, 409)
        self.issues = issues or [{"code": code, "message": message, "severity": "blocker"}]


@dataclass(frozen=True)
class TrialAdoptionEvidence:
    scenario_ref: str
    draft_ref: str
    baseline: Dict[str, Any]
    snapshot: Dict[str, Any]
    prepared: Any
    payload: Any

