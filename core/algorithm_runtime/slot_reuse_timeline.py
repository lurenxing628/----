"""Run-owned resource timeline container shared by the overlap cache and the owned segment lists."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .slot_overlap_reuse import SlotOverlapReuse

Segment = Tuple[datetime, datetime]


class SlotReuseTimeline(Dict[str, List[Segment]]):
    """Run-owned dict; all timeline reads and writes retain ordinary dict semantics."""

    def __init__(self) -> None:
        super().__init__()
        self.overlap_reuse: Optional[SlotOverlapReuse] = None
