"""Internal candidate computation artifacts, never a persisted RunResult."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from core.services.scheduler.run.schedule_orchestrator import ScheduleOrchestrationOutcome
    from core.services.workbench.run_input import CandidateRunInput


@dataclass(frozen=True)
class CandidateRunComputation:
    schedule_input: "CandidateRunInput"
    orchestration: "ScheduleOrchestrationOutcome"
    candidate_payloads: Dict[str, Any]
    dispositions: List[Dict[str, Any]]
    state: str
    result_persisted: bool = field(default=False, init=False)


class CandidateRunInputError(ValueError):
    def __init__(self, reason: str, message: str, *, issues=None):
        super().__init__(message)
        self.code = reason
        self.reason = reason
        self.issues = list(issues or [])
        self.can_adopt = False
        self.result_persisted = False
