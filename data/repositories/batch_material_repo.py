from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models import BatchMaterial

from .base_repo import BaseRepository


class BatchMaterialRepository(BaseRepository):
    """批次物料需求仓库（BatchMaterials）。"""

    def get(self, bm_id: int) -> Optional[BatchMaterial]:
        row = self.fetchone(
            "SELECT id, batch_id, material_id, required_qty, available_qty, ready_status FROM BatchMaterials WHERE id = ?",
            (int(bm_id),),
        )
        return BatchMaterial.from_row(row) if row else None

    def exists(self, batch_id: str, material_id: str) -> bool:
        return bool(
            self.fetchvalue(
                "SELECT 1 FROM BatchMaterials WHERE batch_id = ? AND material_id = ? LIMIT 1",
                (str(batch_id), str(material_id)),
            )
        )

    def list_by_batch(self, batch_id: str) -> List[BatchMaterial]:
        rows = self.fetchall(
            "SELECT id, batch_id, material_id, required_qty, available_qty, ready_status FROM BatchMaterials WHERE batch_id = ? ORDER BY id",
            (str(batch_id),),
        )
        return [BatchMaterial.from_row(r) for r in rows]

    def add(self, batch_id: str, material_id: str, *, required_qty: float, available_qty: float, ready_status: str) -> BatchMaterial:
        cur = self.execute(
            """
            INSERT INTO BatchMaterials (batch_id, material_id, required_qty, available_qty, ready_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(batch_id), str(material_id), float(required_qty), float(available_qty), str(ready_status)),
        )
        return BatchMaterial(
            id=int(cur.lastrowid) if cur.lastrowid is not None else None,
            batch_id=str(batch_id),
            material_id=str(material_id),
            required_qty=float(required_qty),
            available_qty=float(available_qty),
            ready_status=str(ready_status),
        )

    def update_qty(self, bm_id: int, *, required_qty: Optional[float] = None, available_qty: Optional[float] = None, ready_status: Optional[str] = None) -> int:
        updates: Dict[str, Any] = {"required_qty": required_qty, "available_qty": available_qty, "ready_status": ready_status}
        self.execute(
            """
            UPDATE BatchMaterials
            SET
              required_qty = COALESCE(?, required_qty),
              available_qty = COALESCE(?, available_qty),
              ready_status = COALESCE(?, ready_status)
            WHERE id = ?
            """,
            (updates.get("required_qty"), updates.get("available_qty"), updates.get("ready_status"), int(bm_id)),
        )
        return 1

    def delete(self, bm_id: int) -> None:
        self.execute("DELETE FROM BatchMaterials WHERE id = ?", (int(bm_id),))

    def delete_by_batch(self, batch_id: str) -> int:
        cur = self.execute("DELETE FROM BatchMaterials WHERE batch_id = ?", (str(batch_id),))
        return int(getattr(cur, "rowcount", 0) or 0)

