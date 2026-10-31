from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .downtime import SegmentOverlapIndex
from .owned_timeline import owned_segment_certificate
from .slot_reuse_timeline import Segment, SlotReuseTimeline


class SlotOverlapReuse:
    """One latest, exact segment snapshot per resource, owned by one SGS run."""

    def __init__(self) -> None:
        self._owned_certificate = owned_segment_certificate
        self._entries: Dict[Tuple[str, str], Tuple[Tuple[Segment, ...], SegmentOverlapIndex]] = {}
        self._certificates: Dict[Tuple[str, str], Any] = {}
        self._downtime_sources: Dict[str, Tuple[Any, int]] = {}

    def _reuse_downtime(self, resource_id: str, segments: Sequence[Segment],
                        entry: Optional[Tuple[Tuple[Segment, ...], SegmentOverlapIndex]]) -> Optional[SegmentOverlapIndex]:
        if entry is None:
            return None
        if not segments and not entry[0]:
            entry[1].begin_estimate()
            return entry[1]
        source = self._downtime_sources.get(resource_id)
        if source is not None and source[0] is segments and source[1] == len(segments):
            entry[1].begin_estimate()
            return entry[1]
        return None

    def index(self, kind: str, resource_id: str, segments: Sequence[Segment]) -> SegmentOverlapIndex:
        key = (kind, resource_id)
        entry = self._entries.get(key)
        if kind == "downtime":
            reused = self._reuse_downtime(resource_id, segments, entry)
            if reused is not None:
                return reused
        # Short immutable snapshots are cheaper than certifying an owner's full protocol.
        # Inspect the previous snapshot, not the caller's mutable sequence (no extra reads).
        certificate = self._owned_certificate(segments) if entry is not None and len(entry[0]) >= 128 else None
        if certificate is not None and entry is not None and self._certificates.get(key) == certificate:
            entry[1].begin_estimate()
            return entry[1]
        # Unknown/borrowed sequences still require exact content equality, including same-length edits.
        # The immutable snapshot also keeps older indexes independent of later owner mutations.
        snapshot = segments if isinstance(segments, tuple) else tuple(segments)
        if entry is None or entry[0] != snapshot:
            derived = entry[1].with_appended_segment(snapshot) if entry is not None else None
            index = derived if derived is not None else SegmentOverlapIndex(snapshot)
            self._entries[key] = (snapshot, index)
        else:
            index = entry[1]
        if kind == "downtime":
            self._downtime_sources[resource_id] = (segments, len(snapshot))
        if len(snapshot) >= 128 and (entry is None or len(entry[0]) < 128):
            certificate = self._owned_certificate(segments)
        self._certificates[key] = certificate
        index.begin_estimate()
        return index


class _ShortSlotOverlapReuse(SlotOverlapReuse):
    """The original snapshot path, selected once for a small decode."""

    def index(self, kind: str, resource_id: str, segments: Sequence[Segment]) -> SegmentOverlapIndex:
        key = (kind, resource_id)
        entry = self._entries.get(key)
        if kind == "downtime":
            reused = self._reuse_downtime(resource_id, segments, entry)
            if reused is not None:
                return reused
        snapshot = segments if isinstance(segments, tuple) else tuple(segments)
        if entry is None or entry[0] != snapshot:
            derived = entry[1].with_appended_segment(snapshot) if entry is not None else None
            index = derived if derived is not None else SegmentOverlapIndex(snapshot)
            self._entries[key] = (snapshot, index)
        else:
            index = entry[1]
        if kind == "downtime":
            self._downtime_sources[resource_id] = (segments, len(snapshot))
        index.begin_estimate()
        return index


def overlap_reuse_for(timeline: Dict[str, List[Segment]]) -> Optional[SlotOverlapReuse]:
    return timeline.overlap_reuse if isinstance(timeline, SlotReuseTimeline) else None


@contextmanager
def sgs_overlap_reuse(timeline: Dict[str, List[Segment]], *, expected_operations: int) -> Iterator[None]:
    # Borrowed legacy dicts stay untouched, including their identity and aliases.
    if not isinstance(timeline, SlotReuseTimeline):
        yield
        return
    previous = timeline.overlap_reuse
    timeline.overlap_reuse = _ShortSlotOverlapReuse() if expected_operations < 128 else SlotOverlapReuse()
    try:
        yield
    finally:
        timeline.overlap_reuse = previous
