"""Candidate adoption is a new official identity, never a candidate plan alias."""

from dataclasses import dataclass
from typing import Any, Dict, Union

from core.models.workbench_command import WorkbenchCommandRejected

ADOPT_ACTION = "scheduling.candidate.adopt"


class CandidateAdoptionBlocked(WorkbenchCommandRejected):
    def __init__(self, code, message):
        super().__init__(code, message, 409)


@dataclass(frozen=True)
class CandidateAdoptionEvidence:
    candidate_ref: str
    run_ref: str
    baseline: Dict[str, Any]
    snapshot: Dict[str, Any]
    prepared: Any
    payload: Any


def adoption_input(value):
    if type(value) is not dict or set(value) != {"confirm", "reason", "declared_operator"}:
        raise WorkbenchCommandRejected("invalid_input", "采用须提供确认、原因和声明操作人，不能夹带其他字段。", 400)
    if value["confirm"] is not True:
        raise WorkbenchCommandRejected("invalid_input", "请明确确认正式采用。", 422)
    result: Dict[str, Union[bool, str]] = {"confirm": True}
    for key, limit in (("reason", 1000), ("declared_operator", 100)):
        text = value[key]
        if type(text) is not str or not text.strip() or len(text) > limit or "\x00" in text:
            raise WorkbenchCommandRejected("invalid_input", "采用原因或声明操作人为空、过长或含无效字符。", 422)
        result[key] = text.strip()
    return result
