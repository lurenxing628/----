from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CriticalChainSnapshot:
    """Materialized detail rows shared by cache identity and chain computation."""

    rows: List[Dict[str, Any]]

    def fingerprint(self) -> str:
        # Hash every returned column, including joined labels and fallback IDs.
        # Keep row order: duplicate task IDs are resolved by the last loaded row.
        digest = hashlib.sha256(b"critical-chain-detail-rows-v1\n")
        for row in self.rows:
            payload = json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            digest.update(payload.encode("ascii"))
            digest.update(b"\n")
        return digest.hexdigest()

    def list_by_version_with_details(self, version: int) -> List[Dict[str, Any]]:
        """Use the adopted calculator without issuing a second database read."""
        return self.rows
