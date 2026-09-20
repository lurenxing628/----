"""零件动作事实读仓储：选中模板的完整原始行（含隐藏字段与保留历史）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository


class WorkbenchProcessPartFactsRepository(BaseRepository):
    def part(self, part_no: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM Parts WHERE part_no=?", (part_no,))

    def identity(self, ref: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM WorkbenchEntityRefs WHERE ref=?", (ref,))

    def operations(self, part_no: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM PartOperations WHERE part_no=? ORDER BY id", (part_no,))

    def groups(self, part_no: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM ExternalGroups WHERE part_no=? ORDER BY group_id", (part_no,))

    def batches(self, part_no: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM Batches WHERE part_no=? ORDER BY batch_id", (part_no,))

    def foreign_group_members(self, part_no: str) -> List[Dict[str, Any]]:
        """别的零件上、却挂在本零件外协组里的工序。"""
        return self.fetchall("""SELECT o.* FROM PartOperations o
                JOIN ExternalGroups g ON g.group_id=o.ext_group_id
                WHERE g.part_no=? AND o.part_no<>? ORDER BY o.id""", (part_no, part_no))

    def template_identities(self, part_no: str) -> List[Dict[str, Any]]:
        return self.fetchall("""SELECT * FROM WorkbenchEntityRefs WHERE active=1 AND (
            (kind='template_operation' AND entity_key IN (
                SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no=?)) OR
            (kind='template_external_group' AND entity_key IN (
                SELECT group_id FROM ExternalGroups WHERE part_no=?))) ORDER BY ref""", (part_no, part_no))

    def workflow(self, part_ref: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM WorkbenchProcessWorkflow WHERE part_ref=?", (part_ref,))

    def confirmations(self, part_ref: str) -> List[Dict[str, Any]]:
        return self.fetchall("""SELECT * FROM WorkbenchProcessOperationConfirmations
                WHERE part_ref=? ORDER BY operation_ref,stage""", (part_ref,))
