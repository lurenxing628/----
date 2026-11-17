"""A run's receipt (``WorkbenchRunReceipts.result_json``) as one of its two real forms.

A run that saved candidate results keeps their manifest, selection, operation dispositions, summary, process and
requirement ledger (``PersistedReceipt``). A failed or interrupted run saved no candidates (``FailedReceipt``); only a
failed one records the internal error it failed with. Writers build these values directly and store ``document()``;
``CandidateStore.receipt`` admits a stored body back into the same form once.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

PERSISTED_RECEIPT_KEYS = (
    "result_persisted", "state", "error", "candidates", "selection", "dispositions", "summary", "unified_process",
    "operation_effort",
)
FAILED_RECEIPT_KEYS = ("state", "result_persisted", "candidates", "error")
FAILED_RECEIPT_OPTIONAL_KEYS = ("diagnostic",)


@dataclass(frozen=True)
class PersistedReceipt:
    state: str
    candidates: List[Dict[str, Any]]
    selection: Dict[str, Any]
    dispositions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    unified_process: Dict[str, Any]
    operation_effort: Dict[str, Any]

    def document(self) -> Dict[str, Any]:
        return {
            "result_persisted": True, "state": self.state, "error": None, "candidates": self.candidates,
            "selection": self.selection, "dispositions": self.dispositions, "summary": self.summary,
            "unified_process": self.unified_process, "operation_effort": self.operation_effort,
        }


@dataclass(frozen=True)
class FailedReceipt:
    """``diagnostic`` is the internal error a failed run recorded; an interrupted run has none."""

    state: str
    error: Dict[str, str]
    diagnostic: Optional[Dict[str, str]]

    def document(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"state": self.state, "result_persisted": False, "candidates": [], "error": self.error}
        if self.diagnostic is not None:
            result["diagnostic"] = self.diagnostic
        return result


RunReceipt = Union[PersistedReceipt, FailedReceipt]
