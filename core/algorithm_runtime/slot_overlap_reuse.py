from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from .downtime import SegmentOverlapIndex

Segment = Tuple[datetime, datetime]


class SlotOverlapReuse:
    """One latest, exact segment snapshot per resource, owned by one SGS run."""

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str], Tuple[Tuple[Segment, ...], SegmentOverlapIndex]] = {}

    def index(self, kind: str, resource_id: str, segments: Optional[Sequence[Segment]]) -> SegmentOverlapIndex:
        # Content equality also catches same-length edits, replacements and gap inserts.
        # Never keep a mutable timeline reference in an index reused across estimates.
        snapshot = tuple(segments or ())
        key = (kind, resource_id)
        entry = self._entries.get(key)
        if entry is None or entry[0] != snapshot:
            derived = entry[1].with_appended_segment(snapshot) if entry is not None else None
            index = derived if derived is not None else SegmentOverlapIndex(snapshot)
            self._entries[key] = (snapshot, index)
        else:
            index = entry[1]
        index.begin_estimate()
        return index


class SlotReuseTimeline(Dict[str, List[Segment]]):
    """Run-owned dict; all timeline reads and writes retain ordinary dict semantics."""

    def __init__(self) -> None:
        super().__init__()
        self.overlap_reuse: Optional[SlotOverlapReuse] = None


def overlap_reuse_for(timeline: Dict[str, List[Segment]]) -> Optional[SlotOverlapReuse]:
    return timeline.overlap_reuse if isinstance(timeline, SlotReuseTimeline) else None


@contextmanager
def sgs_overlap_reuse(timeline: Dict[str, List[Segment]]) -> Iterator[None]:
    # Borrowed legacy dicts stay untouched, including their identity and aliases.
    if not isinstance(timeline, SlotReuseTimeline):
        yield
        return
    previous = timeline.overlap_reuse
    timeline.overlap_reuse = SlotOverlapReuse()
    try:
        yield
    finally:
        timeline.overlap_reuse = previous
