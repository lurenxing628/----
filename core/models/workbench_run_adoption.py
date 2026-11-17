"""Candidate adoption is a new official identity, never a candidate plan alias."""

from dataclasses import dataclass
from typing import Any, Dict, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.filled_text import is_filled_text
from core.shared.key_sets import keys_conform

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
    outcome: Any
    provenance: Dict[str, Any]
    task_snapshots: Dict[int, Dict[str, Any]]


def adoption_input(value):
    if not keys_conform(value, ("confirm", "reason", "declared_operator")):
        raise WorkbenchCommandRejected("invalid_input", "采用要填写原因和经办人，并勾选确认；不要带其他内容。", 400)
    if value["confirm"] is not True:
        raise WorkbenchCommandRejected("invalid_input", "请勾选确认后再正式采用。", 422)
    result: Dict[str, Union[bool, str]] = {"confirm": True}
    for key, limit in (("reason", 1000), ("declared_operator", 100)):
        text = value[key]
        if not is_filled_text(text, limit):
            raise WorkbenchCommandRejected("invalid_input", "采用原因或声明操作人为空、过长或含无效字符。", 422, fields=(key,))
        result[key] = text.strip()
    return result
