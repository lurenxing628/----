"""Degradation rule for capture-period checkpoint failures of graph decodes.

Capturing decode checkpoints needs a checkpoint request, whose input signature can be refused for
unsupported inputs or calendars. Such capture-period failures degrade to a plain full decode with the
reason recorded; only a *resumed* decode's checkpoint mismatch stays fail-loud, because after a
rollback-safe adoption it can only mean a real bug.
"""
from __future__ import annotations

from core.algorithms.greedy.dispatch.sgs_checkpoint import CHECKPOINT_FIELD
from core.infrastructure.errors import ValidationError


def is_capture_failure(exc: ValidationError, *, resumed: bool) -> bool:
    """Checkpoint errors of a decode that resumed nothing are capture failures; resumed mismatches stay loud."""
    if str(getattr(exc, "field", "") or "") != CHECKPOINT_FIELD:
        return False
    return not resumed


def capture_failure_reason(exc: ValidationError) -> str:
    details = getattr(exc, "details", None)
    reason = str((details or {}).get("reason") or "").strip() if isinstance(details, dict) else ""
    return reason or "decode_checkpoint_capture_failed"


__all__ = ["capture_failure_reason", "is_capture_failure"]
