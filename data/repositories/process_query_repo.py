"""Template-operation reference and part reference reads for the shared process services.

Rows are returned as stored; permanent-reference and deletion
judgements stay with the calling service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class ProcessQueryRepository(BaseRepository):
    def batch_references_part(self, part_no: str) -> bool:
        return self.execute("SELECT 1 FROM Batches WHERE part_no = ? LIMIT 1", (part_no,)).fetchone() is not None

    def template_operation_ref(self, part_no: str, seq: Any) -> Optional[Dict[str, Any]]:
        """{"ref": ...} for the active template operation at (part_no, seq); ref is None without a live reference."""
        return self.fetchone("""SELECT r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            WHERE o.part_no=? AND o.seq=? AND o.status='active'""", (part_no, seq))

    def template_operations_by_refs(self, refs: Sequence[str]) -> List[Dict[str, Any]]:
        """Active template operations joined to their live references, read in bounded chunks."""
        rows: List[Dict[str, Any]] = []
        for chunk in chunks(refs):
            rows.extend(self.fetchall("""SELECT o.*,r.ref,r.revision FROM WorkbenchEntityRefs r
                JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.status='active'
                AND r.ref IN (""" + ",".join("?" for _ in chunk) + ")", chunk))
        return rows
