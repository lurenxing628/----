from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import BatchMaterial

from .base_repo import BaseRepository


class _UnsetType:
    pass


_UNSET = _UnsetType()


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

    def list_with_material_details_by_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT bm.id, bm.batch_id, bm.material_id, m.name AS material_name, m.spec, m.unit,
                   bm.required_qty, bm.available_qty, bm.ready_status
            FROM BatchMaterials bm
            LEFT JOIN Materials m ON m.material_id = bm.material_id
            WHERE bm.batch_id = ?
            ORDER BY bm.id
            """,
            (str(batch_id),),
        )

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

    def update_qty(
        self,
        bm_id: int,
        *,
        required_qty: Union[Optional[float], _UnsetType] = _UNSET,
        available_qty: Union[Optional[float], _UnsetType] = _UNSET,
        ready_status: Union[Optional[str], _UnsetType] = _UNSET,
    ) -> int:
        # 仅更新“调用方显式传入”的字段；显式 None 允许置空（对可空列）
        updates: Dict[str, Any] = {}
        if required_qty is not _UNSET:
            updates["required_qty"] = required_qty
        if available_qty is not _UNSET:
            updates["available_qty"] = available_qty
        if ready_status is not _UNSET:
            updates["ready_status"] = ready_status

        if not updates:
            return 0

        set_parts: List[str] = []
        params: List[Any] = []
        for key in ("required_qty", "available_qty", "ready_status"):
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        params.append(int(bm_id))
        sql = f"UPDATE BatchMaterials SET {', '.join(set_parts)} WHERE id = ?"
        cur = self.execute(sql, tuple(params))
        return int(getattr(cur, "rowcount", 0) or 0)

    def delete(self, bm_id: int) -> None:
        self.execute("DELETE FROM BatchMaterials WHERE id = ?", (int(bm_id),))

    def delete_by_batch(self, batch_id: str) -> int:
        cur = self.execute("DELETE FROM BatchMaterials WHERE batch_id = ?", (str(batch_id),))
        return int(getattr(cur, "rowcount", 0) or 0)

