"""Optional per-operation material release; an operation without one keeps its earliest start."""

from __future__ import annotations

from datetime import datetime

from .types import OpForScheduleAlgo


def released_start(op: OpForScheduleAlgo, earliest: datetime) -> datetime:
    """``material_ready_date`` is the release day's midnight, parsed once when the run input is built."""
    release = op.material_ready_date
    return earliest if release is None else max(earliest, release)
