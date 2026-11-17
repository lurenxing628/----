"""The saved source one history entry is read from, as one of its four real forms.

A run entry reads its run archive (``RunPacket``); a metric read that needs only a run candidate's decision reads
the run's admitted input and that candidate's ref (``LightRunPacket``); a trial adoption entry reads its saved
scenario (``TrialPacket``). A comparison side without a chosen entry, and an entry whose adoption audit is missing,
read nothing (``UnavailablePacket``). Readers branch on the form once.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Union

from core.models.workbench_run_receipt import PersistedReceipt, RunReceipt
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.trial_origin import TrialOrigin


@dataclass(frozen=True)
class UnavailablePacket:
    """A source this read cannot use: ``kind`` is ``empty`` (no entry chosen, ``ref`` None) or the entry's own kind."""

    kind: str
    ref: Optional[str]
    entry_ref: Optional[str]
    source_issue: Dict[str, str]


@dataclass(frozen=True)
class RunPacket:
    """A run's archive: its capture and generation facts, its receipt (None while the run is queued or running), and
    the entry's candidate with its saved tasks when the entry names one."""

    kind: ClassVar[str] = "run"
    ref: str
    entry_ref: str
    capture: Mapping[str, Any]
    facts: GenerationFacts
    receipt: Optional[RunReceipt]
    candidate: Optional[Dict[str, Any]]
    raw_tasks: Optional[List[Dict[str, Any]]]

    @property
    def candidate_ref(self) -> Optional[str]:
        return self.candidate["candidate_ref"] if self.candidate is not None else None

    @property
    def selection(self) -> Optional[Dict[str, Any]]:
        """The business selection the run saved with its candidates; a run without saved results has none."""
        return self.receipt.selection if isinstance(self.receipt, PersistedReceipt) else None


@dataclass(frozen=True)
class LightRunPacket:
    """A run entry read for one candidate's metrics: the run's admitted input and that candidate's ref."""

    kind: ClassVar[str] = "run"
    ref: str
    entry_ref: str
    run_input: Dict[str, Any]
    candidate_ref: str


@dataclass(frozen=True)
class TrialPacket:
    """A saved scenario: its snapshot, its draft head, its rows bound to the draft and the trial's origin."""

    kind: ClassVar[str] = "trial"
    ref: str
    entry_ref: str
    saved: Dict[str, Any]
    head: Dict[str, Any]
    rows: List[Dict[str, Any]]
    origin: TrialOrigin


HistoryPacket = Union[UnavailablePacket, RunPacket, LightRunPacket, TrialPacket]
