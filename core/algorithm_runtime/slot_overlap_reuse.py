from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .downtime import SegmentOverlapIndex
from .owned_timeline import owned_segment_certificate
from .slot_reuse_timeline import Segment, SlotReuseTimeline


def _segment_snapshot(segments: Optional[Sequence[Segment]]) -> Tuple[Segment, ...]:
    return tuple(segments or ())


class SlotOverlapReuse:
    """One latest, exact segment snapshot per resource, owned by one SGS run."""

    def __init__(self) -> None:
        self._owned_certificate = owned_segment_certificate
        self._entries: Dict[Tuple[str, str], Tuple[Tuple[Segment, ...], SegmentOverlapIndex]] = {}
        self._certificates: Dict[Tuple[str, str], Any] = {}

    def index(self, kind: str, resource_id: str, segments: Optional[Sequence[Segment]]) -> SegmentOverlapIndex:
        key = (kind, resource_id)
        entry = self._entries.get(key)
        # Short immutable snapshots are cheaper than certifying an owner's full protocol.
        # Inspect the previous snapshot, not the caller's mutable sequence (no extra reads).
        certificate = self._owned_certificate(segments) if entry is not None and len(entry[0]) >= 128 else None
        if certificate is not None and entry is not None and self._certificates.get(key) == certificate:
            entry[1].begin_estimate()
            return entry[1]
        # Unknown/borrowed sequences still require exact content equality, including same-length edits.
        # The immutable snapshot also keeps older indexes independent of later owner mutations.
        snapshot = _segment_snapshot(segments)
        if entry is None or entry[0] != snapshot:
            derived = entry[1].with_appended_segment(snapshot) if entry is not None else None
            index = derived if derived is not None else SegmentOverlapIndex(snapshot)
            self._entries[key] = (snapshot, index)
        else:
            index = entry[1]
        if len(snapshot) >= 128 and (entry is None or len(entry[0]) < 128):
            certificate = self._owned_certificate(segments)
        self._certificates[key] = certificate
        index.begin_estimate()
        return index


class _ShortSlotOverlapReuse(SlotOverlapReuse):
    """The original snapshot path, selected once for a small decode."""

    def index(self, kind: str, resource_id: str, segments: Optional[Sequence[Segment]]) -> SegmentOverlapIndex:
        key = (kind, resource_id)
        snapshot = tuple(segments or ())
        entry = self._entries.get(key)
        if entry is None or entry[0] != snapshot:
            derived = entry[1].with_appended_segment(snapshot) if entry is not None else None
            index = derived if derived is not None else SegmentOverlapIndex(snapshot)
            self._entries[key] = (snapshot, index)
        else:
            index = entry[1]
        index.begin_estimate()
        return index


def overlap_reuse_for(timeline: Dict[str, List[Segment]]) -> Optional[SlotOverlapReuse]:
    return timeline.overlap_reuse if isinstance(timeline, SlotReuseTimeline) else None


@contextmanager
def sgs_overlap_reuse(timeline: Dict[str, List[Segment]], *, expected_operations: Optional[int] = None) -> Iterator[None]:
    # Borrowed legacy dicts stay untouched, including their identity and aliases.
    if not isinstance(timeline, SlotReuseTimeline):
        yield
        return
    previous = timeline.overlap_reuse
    timeline.overlap_reuse = (_ShortSlotOverlapReuse() if expected_operations is not None and expected_operations < 128
                             else SlotOverlapReuse())
    try:
        yield
    finally:
        timeline.overlap_reuse = previous
