from __future__ import annotations

from typing import Any, Dict

from core.models.part import Part

from .base_repo import BaseRepository


class PartRepository(BaseRepository):
    """零件仓库（Parts）。"""

    def create(self, part: Part) -> None:
        self.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            (part.part_no, part.part_name, part.route_raw, part.route_parsed, part.remark),
        )

    def update(self, part_no: str, updates: Dict[str, Any]) -> None:
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [*updates.values(), part_no]
        sql = f"UPDATE Parts SET {', '.join(set_parts)} WHERE part_no = ?"
        self.execute(sql, tuple(params))

    def delete(self, part_no: str) -> None:
        self.execute("DELETE FROM Parts WHERE part_no = ?", (part_no,))
