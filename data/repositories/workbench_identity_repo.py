"""Read persisted identities only; GET requests never allocate or repair them."""

from __future__ import annotations

import json
from typing import Dict, Iterable, Optional

from core.models.workbench_identity import WorkbenchEntityIdentity

from .base_repo import BaseRepository


def _identity(row) -> Optional[WorkbenchEntityIdentity]:
    return None if row is None else WorkbenchEntityIdentity.from_row(row)


class WorkbenchIdentityRepository(BaseRepository):
    def get(self, ref: str) -> Optional[WorkbenchEntityIdentity]:
        return _identity(self.fetchone("SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE ref = ?", (ref,)))

    def find_active(self, kind: str, key: str) -> Optional[WorkbenchEntityIdentity]:
        return _identity(self.fetchone("SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE kind = ? AND entity_key = ? AND active = 1", (kind, key)))

    def active_map(self, kind: str, keys: Iterable[str]) -> Dict[str, WorkbenchEntityIdentity]:
        rows = self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE kind = ? AND active = 1 AND entity_key IN (SELECT value FROM json_each(?)) ORDER BY entity_key, ref",
            (kind, json.dumps(list(keys))),
        )
        return {row["entity_key"]: WorkbenchEntityIdentity.from_row(row) for row in rows}

    def map_by_refs(self, refs: Iterable[str]) -> Dict[str, WorkbenchEntityIdentity]:
        rows = self.fetchall(
            "SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE ref IN (SELECT value FROM json_each(?))",
            (json.dumps(list(refs)),),
        )
        return {row["ref"]: WorkbenchEntityIdentity.from_row(row) for row in rows}
