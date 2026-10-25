from __future__ import annotations

from typing import Optional, cast

from .base_repo import BaseRepository


class BatchMaterialRepository(BaseRepository):
    """批次物料需求仓库（BatchMaterials）。"""

    def copy_requirements(self, target_batch_id, operation_map, *, requirements):
        """Copy demand and exact use-operation binding, never another batch's arrivals."""
        from .batch_material_stage_repo import BatchMaterialStageRepository
        stages = BatchMaterialStageRepository(self.conn)
        for row in requirements:
            operation_id = row["operation_id"]
            target_operation_id = None
            if operation_id is not None:
                if operation_id not in operation_map:
                    raise ValueError("复制物料需求时缺少使用工序的对应关系，未保存。")
                target_operation_id = operation_map[operation_id]
            created_id = self.add(target_batch_id, row["material_id"], required_qty=row["required_qty"], available_qty=0, ready_status="no")
            if target_operation_id is not None:
                stages.replace_operation(created_id, target_operation_id)

    def add(self, batch_id: str, material_id: str, *, required_qty: float, available_qty: float, ready_status: str) -> int:
        cur = self.execute(
            """
            INSERT INTO BatchMaterials (batch_id, material_id, required_qty, available_qty, ready_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(batch_id), str(material_id), float(required_qty), float(available_qty), str(ready_status)),
        )
        return cast(int, cur.lastrowid)

    def update_qty(
        self,
        bm_id: int,
        *,
        required_qty: Optional[float],
        available_qty: Optional[float],
        ready_status: Optional[str],
    ) -> None:
        self.execute(
            "UPDATE BatchMaterials SET required_qty = ?, available_qty = ?, ready_status = ? WHERE id = ?",
            (required_qty, available_qty, ready_status, int(bm_id)),
        )

    def delete(self, bm_id: int) -> None:
        self.execute("DELETE FROM BatchMaterials WHERE id = ?", (int(bm_id),))

