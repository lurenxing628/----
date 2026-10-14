from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.models.content import content_text


@dataclass
class CriticalChainSnapshot:
    """Materialized detail rows shared by cache identity and chain computation."""

    rows: List[Dict[str, Any]]

    def content_key(self) -> str:
        # Compare every returned column, including joined labels and fallback IDs.
        # Keep row order: duplicate task IDs are resolved by the last loaded row.
        return content_text(self.rows)

    def list_by_version_with_details(self, version: int) -> List[Dict[str, Any]]:
        """Use the adopted calculator without issuing a second database read."""
        return self.rows
