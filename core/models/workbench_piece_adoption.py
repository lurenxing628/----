"""Internal evidence only: neither a public adoption capability nor a new identity."""

from dataclasses import dataclass
from typing import Optional, Tuple

from core.models.workbench_run_adoption import CandidateAdoptionBlocked


class PieceAdoptionBlocked(CandidateAdoptionBlocked):
    def __init__(self, code, message, *, batch_id=None):
        super().__init__(code, message)
        self.batch_id = batch_id


@dataclass(frozen=True)
class PieceOperationWork:
    op_id: int
    batch_id: str
    piece_id: Optional[str]
    sequence: int
    target_quantity: int
    predecessor_op_ids: Tuple[int, ...]


@dataclass(frozen=True)
class PieceAdoptionScope:
    operations: Tuple[PieceOperationWork, ...]


@dataclass(frozen=True)
class PieceAdoptionEvidence:
    scope: PieceAdoptionScope
    operation_refs: Tuple[Tuple[int, str], ...]
    protected_op_ids: Tuple[int, ...]
    execution_snapshot_revision: str
