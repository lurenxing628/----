"""Read persisted identities only; GET requests never allocate or repair them."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from core.models.workbench_identity import WorkbenchEntityIdentity

from .base_repo import BaseRepository


def _identity(row) -> Optional[WorkbenchEntityIdentity]:
    if row is None:
        return None
    return WorkbenchEntityIdentity(ref=row["ref"], kind=row["kind"], entity_key=row["entity_key"],
                                   revision=int(row["revision"]), active=bool(row["active"]))


class WorkbenchIdentityRepository(BaseRepository):
    def get(self, ref: str) -> Optional[WorkbenchEntityIdentity]:
        return _identity(self.fetchone("SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE ref = ?", (ref,)))

    def find_active(self, kind: str, key: str) -> Optional[WorkbenchEntityIdentity]:
        return _identity(self.fetchone("SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE kind = ? AND entity_key = ? AND active = 1", (kind, key)))

    def active_map(self, kind: str, keys: Iterable[str]) -> Dict[str, WorkbenchEntityIdentity]:
        values = list(dict.fromkeys(keys))
        output = {}
        for start in range(0, len(values), 500):
            chunk = values[start:start + 500]
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT ref, kind, entity_key, revision, active FROM WorkbenchEntityRefs WHERE kind = ? AND active = 1 AND entity_key IN (" + marks + ")", [kind] + chunk)
            for row in rows:
                identity = _identity(row)
                if identity is not None:
                    output[identity.entity_key] = identity
        return output
