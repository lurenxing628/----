from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from data.repositories import BatchMaterialRepository, BatchRepository, MaterialRepository


class BatchMaterialService:
    """批次物料需求与齐套判定服务（BatchMaterials）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx = TransactionManager(conn)
        self.batch_repo = BatchRepository(conn, logger=logger)
        self.mat_repo = MaterialRepository(conn, logger=logger)
        self.repo = BatchMaterialRepository(conn, logger=logger)

    @staticmethod
    def _norm_text(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s != "" else None

    @staticmethod
    def _norm_float_required(v: Any, field: str, *, min_v: float = 0.0) -> float:
        raw = "" if v is None else str(v).strip()
        if raw == "":
            raise ValidationError(f"“{field}”不能为空", field=field)
        try:
            x = float(raw)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)
        if x < min_v:
            raise ValidationError(f"“{field}”不能小于 {min_v}", field=field)
        return float(x)

    def list_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        bid = self._norm_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="batch_id")
        rows = self.conn.execute(
            """
            SELECT bm.id, bm.batch_id, bm.material_id, m.name AS material_name, m.spec, m.unit,
                   bm.required_qty, bm.available_qty, bm.ready_status
            FROM BatchMaterials bm
            LEFT JOIN Materials m ON m.material_id = bm.material_id
            WHERE bm.batch_id = ?
            ORDER BY bm.id
            """,
            (bid,),
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "batch_id": r["batch_id"],
                    "material_id": r["material_id"],
                    "material_name": r["material_name"],
                    "spec": r["spec"],
                    "unit": r["unit"],
                    "required_qty": r["required_qty"],
                    "available_qty": r["available_qty"],
                    "ready_status": r["ready_status"],
                }
            )
        return result

    def add_requirement(self, batch_id: Any, material_id: Any, required_qty: Any, available_qty: Any = 0) -> None:
        bid = self._norm_text(batch_id)
        mid = self._norm_text(material_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="batch_id")
        if not mid:
            raise ValidationError("“物料ID”不能为空", field="material_id")
        if not self.batch_repo.get(bid):
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{bid}”不存在")
        if not self.mat_repo.get(mid):
            raise BusinessError(ErrorCode.NOT_FOUND, f"物料“{mid}”不存在")
        if self.repo.exists(bid, mid):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "该批次已存在该物料需求，无需重复添加。")

        req = self._norm_float_required(required_qty, field="需求数量", min_v=0.000001)
        avail = self._norm_float_required(available_qty, field="到料数量", min_v=0.0)
        ready = "yes" if avail >= req else "no"

        with self.tx.transaction():
            self.repo.add(bid, mid, required_qty=req, available_qty=avail, ready_status=ready)
            self._recalc_and_sync_batch_ready(bid)
            if self.op_logger is not None:
                self.op_logger.info(
                    module="material",
                    action="batch_material_add",
                    target_type="batch",
                    target_id=bid,
                    detail={"batch_id": bid, "material_id": mid, "required_qty": req, "available_qty": avail, "ready_status": ready},
                )

    def update_requirement(self, bm_id: Any, *, required_qty: Any = None, available_qty: Any = None) -> None:
        try:
            bid_int = int(str(bm_id).strip())
        except Exception:
            raise ValidationError("“ID”不合法", field="id")
        bm = self.repo.get(bid_int)
        if not bm:
            raise BusinessError(ErrorCode.NOT_FOUND, f"批次物料记录不存在：ID={bid_int}")

        req = bm.required_qty
        avail = bm.available_qty
        if required_qty is not None and str(required_qty).strip() != "":
            req = self._norm_float_required(required_qty, field="需求数量", min_v=0.000001)
        if available_qty is not None and str(available_qty).strip() != "":
            avail = self._norm_float_required(available_qty, field="到料数量", min_v=0.0)
        ready = "yes" if avail >= req else "no"

        with self.tx.transaction():
            self.repo.update_qty(bid_int, required_qty=req, available_qty=avail, ready_status=ready)
            self._recalc_and_sync_batch_ready(bm.batch_id)
            if self.op_logger is not None:
                self.op_logger.info(
                    module="material",
                    action="batch_material_update",
                    target_type="batch_material",
                    target_id=str(bid_int),
                    detail={"id": bid_int, "batch_id": bm.batch_id, "material_id": bm.material_id, "required_qty": req, "available_qty": avail, "ready_status": ready},
                )

    def delete_requirement(self, bm_id: Any) -> None:
        try:
            bid_int = int(str(bm_id).strip())
        except Exception:
            raise ValidationError("“ID”不合法", field="id")
        bm = self.repo.get(bid_int)
        if not bm:
            return
        with self.tx.transaction():
            self.repo.delete(bid_int)
            self._recalc_and_sync_batch_ready(bm.batch_id)
            if self.op_logger is not None:
                self.op_logger.info(
                    module="material",
                    action="batch_material_delete",
                    target_type="batch_material",
                    target_id=str(bid_int),
                    detail={"id": bid_int, "batch_id": bm.batch_id, "material_id": bm.material_id},
                )

    # -------------------------
    # 齐套判定与回写
    # -------------------------
    def _calc_batch_ready(self, batch_id: str) -> Tuple[str, Optional[str]]:
        """
        基于 BatchMaterials 判定批次齐套状态。

        规则（最小闭环）：
        - 若该批次没有任何物料需求行：返回 ("", None) 表示“不接管 ready_status”（保留人工/Excel 值）
        - 若全部需求行 ready_status=yes：批次 ready_status=yes，ready_date=今天（若原本已有 ready_date 则保留）
        - 若部分满足：ready_status=partial，ready_date=NULL
        - 全部不满足：ready_status=no，ready_date=NULL
        """
        rows = self.repo.list_by_batch(batch_id)
        if not rows:
            return "", None

        total = len(rows)
        ready_cnt = sum(1 for r in rows if (r.ready_status or "no") == "yes")
        if ready_cnt >= total:
            b = self.batch_repo.get(batch_id)
            if b and b.ready_date:
                return "yes", b.ready_date
            return "yes", date.today().isoformat()
        if ready_cnt > 0:
            return "partial", None
        return "no", None

    def _recalc_and_sync_batch_ready(self, batch_id: str) -> None:
        bid = self._norm_text(batch_id)
        if not bid:
            return
        ready_status, ready_date = self._calc_batch_ready(bid)
        if ready_status == "":
            return
        self.batch_repo.update(bid, {"ready_status": ready_status, "ready_date": ready_date})

