from __future__ import annotations

from typing import Any, Dict, List

from data.repositories import PartOperationRepository


class PartOperationQueryService:
    """零件工序查询服务（只读 façade）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = PartOperationRepository(conn, logger=logger)

    def list_all_active_with_details(self) -> List[Dict[str, Any]]:
        return self.repo.list_all_active_with_details()

    def list_active_hours(self) -> List[Dict[str, Any]]:
        return self.repo.list_active_hours()

    def list_internal_active_hours(self) -> List[Dict[str, Any]]:
        return self.repo.list_internal_active_hours()

    def list_template_snapshot_for_parts(self, part_nos: List[str]) -> List[Dict[str, Any]]:
        snapshot: List[Dict[str, Any]] = []
        normalized_part_nos = sorted({str(part_no or "").strip() for part_no in (part_nos or []) if str(part_no or "").strip()})
        for part_no in normalized_part_nos:
            for op in self.repo.list_by_part(part_no, include_deleted=False):
                snapshot.append(
                    {
                        "part_no": op.part_no,
                        "seq": int(op.seq),
                        "op_type_id": op.op_type_id,
                        "op_type_name": op.op_type_name,
                        "source": op.source,
                        "supplier_id": op.supplier_id,
                        "ext_days": op.ext_days,
                        "setup_hours": op.setup_hours,
                        "unit_hours": op.unit_hours,
                    }
                )
        return snapshot

