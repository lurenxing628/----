from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Part

from .base_repo import BaseRepository


class PartRepository(BaseRepository):
    """零件仓库（Parts）。"""

    def get(self, part_no: str) -> Optional[Part]:
        row = self.fetchone(
            "SELECT part_no, part_name, route_raw, route_parsed, remark, created_at, updated_at FROM Parts WHERE part_no = ?",
            (part_no,),
        )
        return Part.from_row(row) if row else None

    def list(self, route_parsed: Optional[str] = None) -> List[Part]:
        if route_parsed:
            rows = self.fetchall(
                "SELECT part_no, part_name, route_raw, route_parsed, remark, created_at, updated_at FROM Parts WHERE route_parsed = ? ORDER BY part_no",
                (route_parsed,),
            )
        else:
            rows = self.fetchall(
                "SELECT part_no, part_name, route_raw, route_parsed, remark, created_at, updated_at FROM Parts ORDER BY part_no"
            )
        return [Part.from_row(r) for r in rows]

    def list_unparsed(self) -> List[Part]:
        return self.list(route_parsed="no")

    def create(self, part: Union[Part, Dict[str, Any]]) -> Part:
        p = part if isinstance(part, Part) else Part.from_row(part)
        self.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            (p.part_no, p.part_name, p.route_raw, p.route_parsed, p.remark),
        )
        return p

    def update(self, part_no: str, updates: Dict[str, Any]) -> None:
        self.execute(
            "UPDATE Parts SET part_name = COALESCE(?, part_name), route_raw = COALESCE(?, route_raw), route_parsed = COALESCE(?, route_parsed), remark = COALESCE(?, remark), updated_at = CURRENT_TIMESTAMP WHERE part_no = ?",
            (
                updates.get("part_name"),
                updates.get("route_raw"),
                updates.get("route_parsed"),
                updates.get("remark"),
                part_no,
            ),
        )

    def delete(self, part_no: str) -> None:
        self.execute("DELETE FROM Parts WHERE part_no = ?", (part_no,))

