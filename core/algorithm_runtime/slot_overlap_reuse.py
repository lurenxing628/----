from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from .downtime import SegmentOverlapIndex
from .owned_timeline import Segment, owned_segment_certificate


class SlotOverlapReuse:
    """One latest, exact segment snapshot per resource, owned by one SGS run."""

    def __init__(self) -> None:
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
        # Native owners certify (identity, revision) in O(1) without scanning segments.
        certificate = owned_segment_certificate(segments)
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
        self._certificates[key] = certificate
        index.begin_estimate()
        return index
