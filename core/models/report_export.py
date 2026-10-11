"""Report download payload and size-based export decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO


@dataclass
class ReportExport:
    filename: str
    content_type: str
    data: BinaryIO
    mode: str = "direct"
    estimated_rows: int = 0


@dataclass(frozen=True)
class ReportExportDecision:
    mode: str
    estimated_rows: int
