"""Checkpoint reuse for iterated greedy trials: which decode checkpoint a trial order may resume from.

A full decode of a reference order captures checkpoints at evenly spaced pick counts. A trial that
keeps the reference's first ``prefix_length`` operations may resume from that checkpoint; the decoder
re-validates the prefix and fails loudly on any mismatch (see ``dispatch/sgs_checkpoint.py``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpoint, DecodeCheckpointRequest


def checkpoint_positions(size: int, count: int) -> List[int]:
    """Evenly spaced pick counts in [1, size - 1]; fewer than asked when the order is short."""
    if size <= 1 or count <= 0:
        return []
    positions = sorted({max(1, min(size - 1, int(round(size * index / (count + 1))))) for index in range(1, count + 1)})
    return positions


def common_prefix_length(first: Sequence[int], second: Sequence[int]) -> int:
    length = 0
    for left, right in zip(first, second):
        if left != right:
            break
        length += 1
    return length


class CheckpointStore:
    def __init__(self, count: int) -> None:
        self.count = int(count)
        self.full_decodes = 0
        self.resumed_decodes = 0
        self.picks_total = 0
        self.picks_saved = 0
        self.equivalence_checks = 0
        self.disabled_reason: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return self.count > 0 and self.disabled_reason is None

    def disable(self, reason: str) -> None:
        self.disabled_reason = str(reason)

    def request_for(self, size: int) -> Tuple[Optional[DecodeCheckpointRequest], List[DecodeCheckpoint]]:
        captured: List[DecodeCheckpoint] = []
        positions = checkpoint_positions(size, self.count) if self.enabled else []
        if not positions:
            return None, captured
        return DecodeCheckpointRequest(positions, captured.append), captured

    def best_for(self, checkpoints: Sequence[DecodeCheckpoint], *, base_order: Sequence[int],
                 trial_order: Sequence[int]) -> Optional[DecodeCheckpoint]:
        if not self.enabled or not checkpoints:
            return None
        shared = common_prefix_length(base_order, trial_order)
        usable = [item for item in checkpoints if item.prefix_length <= shared]
        if not usable:
            return None
        return max(usable, key=lambda item: item.position)

    def note_decode(self, size: int, *, resumed_from: Optional[DecodeCheckpoint]) -> None:
        self.picks_total += int(size)
        if resumed_from is None:
            self.full_decodes += 1
        else:
            self.resumed_decodes += 1
            self.picks_saved += int(resumed_from.position)

    def summary(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"count": self.count, "full_decodes": self.full_decodes, "resumed_decodes": self.resumed_decodes,
                "picks_total": self.picks_total, "picks_saved": self.picks_saved,
                "equivalence_checks": self.equivalence_checks}
        if self.disabled_reason is not None:
            result["disabled_reason"] = self.disabled_reason
        return result


__all__ = ["CheckpointStore", "checkpoint_positions", "common_prefix_length"]
