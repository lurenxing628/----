from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Material
from data.repositories import MaterialRepository


class MaterialService:
    """物料主数据服务（Materials）。"""

    VALID_STATUS = ("active", "inactive")

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx = TransactionManager(conn)
        self.repo = MaterialRepository(conn, logger=logger)

    @staticmethod
    def _norm_text(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s != "" else None

    @staticmethod
    def _norm_float(v: Any, field: str, *, min_v: float = 0.0) -> float:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 0.0
        try:
            x = float(v)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)
        if x < min_v:
            raise ValidationError(f"“{field}”不能小于 {min_v}", field=field)
        return float(x)

    def list(self, status: Optional[str] = None) -> List[Material]:
        return self.repo.list(status=status)

    def get(self, material_id: str) -> Material:
        mid = self._norm_text(material_id)
        if not mid:
            raise ValidationError("“物料ID”不能为空", field="material_id")
        m = self.repo.get(mid)
        if not m:
            raise BusinessError(ErrorCode.NOT_FOUND, f"物料“{mid}”不存在")
        return m

    def create(self, material_id: Any, name: Any, spec: Any = None, unit: Any = None, stock_qty: Any = 0, status: Any = "active", remark: Any = None) -> Material:
        mid = self._norm_text(material_id)
        if not mid:
            raise ValidationError("“物料ID”不能为空", field="material_id")
        nm = self._norm_text(name)
        if not nm:
            raise ValidationError("“物料名称”不能为空", field="name")
        st = (self._norm_text(status) or "active").lower()
        if st not in self.VALID_STATUS:
            raise ValidationError("“状态”不合法（允许：active/inactive）", field="status")
        qty = self._norm_float(stock_qty, field="库存数量", min_v=0.0)

        if self.repo.exists(mid):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"物料“{mid}”已存在")

        m = Material(
            material_id=mid,
            name=nm,
            spec=self._norm_text(spec),
            unit=self._norm_text(unit),
            stock_qty=qty,
            status=st,
            remark=self._norm_text(remark),
        )
        with self.tx.transaction():
            self.repo.create(m)
            if self.op_logger is not None:
                self.op_logger.info(module="material", action="create", target_type="material", target_id=mid, detail=m.to_dict())
        return m

    def update(self, material_id: str, *, name: Any = None, spec: Any = None, unit: Any = None, stock_qty: Any = None, status: Any = None, remark: Any = None) -> None:
        mid = self._norm_text(material_id)
        if not mid:
            raise ValidationError("“物料ID”不能为空", field="material_id")
        if not self.repo.exists(mid):
            raise BusinessError(ErrorCode.NOT_FOUND, f"物料“{mid}”不存在")

        updates: Dict[str, Any] = {}
        if name is not None and str(name).strip() != "":
            updates["name"] = self._norm_text(name)
        if spec is not None:
            updates["spec"] = self._norm_text(spec)
        if unit is not None:
            updates["unit"] = self._norm_text(unit)
        if stock_qty is not None and str(stock_qty).strip() != "":
            updates["stock_qty"] = self._norm_float(stock_qty, field="库存数量", min_v=0.0)
        if status is not None and str(status).strip() != "":
            st = str(status).strip().lower()
            if st not in self.VALID_STATUS:
                raise ValidationError("“状态”不合法（允许：active/inactive）", field="status")
            updates["status"] = st
        if remark is not None:
            updates["remark"] = self._norm_text(remark)

        if not updates:
            return

        with self.tx.transaction():
            self.repo.update(mid, updates)
            if self.op_logger is not None:
                self.op_logger.info(
                    module="material",
                    action="update",
                    target_type="material",
                    target_id=mid,
                    detail={"material_id": mid, "updates": updates},
                )

    def delete(self, material_id: str) -> None:
        mid = self._norm_text(material_id)
        if not mid:
            raise ValidationError("“物料ID”不能为空", field="material_id")
        if not self.repo.exists(mid):
            return
        with self.tx.transaction():
            self.repo.delete(mid)
            if self.op_logger is not None:
                self.op_logger.info(module="material", action="delete", target_type="material", target_id=mid, detail={"material_id": mid})

