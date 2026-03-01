from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.models.enums import SupplierStatus
from core.services.common.enum_normalizers import normalize_supplier_status
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.process.op_type_service import OpTypeService
from core.services.process.supplier_service import SupplierService
from data.repositories import SupplierRepository


class SupplierExcelImportService:
    """
    供应商配置（Suppliers）Excel 导入落库服务。

    说明：
    - Route 层负责：文件读取、预览、用户确认
    - 本服务负责：按预览结果写库（避免 Route 直接依赖 Repository）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.svc = SupplierService(conn, logger=logger, op_logger=op_logger)
        self.op_type_svc = OpTypeService(conn, logger=logger, op_logger=op_logger)
        self.repo = SupplierRepository(conn, logger=logger)

    @staticmethod
    def _normalize_supplier_status_for_excel(value: Any) -> str:
        return normalize_supplier_status(value)

    def apply_preview_rows(
        self,
        preview_rows: List[Any],
        *,
        mode: ImportMode,
        existing_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        rows = list(preview_rows or [])
        existing_row_ids = set(existing_ids or set())

        def _replace_existing_no_tx() -> None:
            self.svc.ensure_replace_allowed()
            self.repo.delete_all()

        def _row_id_getter(pr: Any) -> str:
            return str((getattr(pr, "data", None) or {}).get("供应商ID") or "").strip()

        def _apply_row_no_tx(pr: Any, existed: bool) -> None:
            data = getattr(pr, "data", None) or {}
            sid = str(data.get("供应商ID") or "").strip()
            if not sid:
                raise ValidationError("“供应商ID”不能为空", field="供应商ID")
            name = str(data.get("名称") or "").strip()
            if not name:
                raise ValidationError("“名称”不能为空", field="名称")
            op_type_id = self.op_type_svc.resolve_op_type_id_optional(data.get("对应工种"))
            default_raw = data.get("默认周期")
            if default_raw is None or (isinstance(default_raw, str) and default_raw.strip() == ""):
                default_days = 1.0
            else:
                try:
                    default_days = float(default_raw)
                except Exception as e:
                    raise ValidationError("“默认周期”必须是数字", field="默认周期") from e
                if default_days <= 0:
                    raise ValidationError("“默认周期”必须大于 0", field="默认周期")

            status = self._normalize_supplier_status_for_excel(data.get("状态"))
            if status not in (SupplierStatus.ACTIVE.value, SupplierStatus.INACTIVE.value):
                raise ValidationError("“状态”不合法（允许：active / inactive；或中文：启用/停用）", field="状态")
            remark = data.get("备注")

            payload = {
                "name": name,
                "op_type_id": op_type_id,
                "default_days": default_days,
                "status": status,
                "remark": remark,
            }
            if existed:
                self.repo.update(sid, payload)
            else:
                self.repo.create({"supplier_id": sid, **payload})

        stats = execute_preview_rows_transactional(
            self.conn,
            mode=mode,
            preview_rows=rows,
            existing_row_ids=existing_row_ids,
            replace_existing_no_tx=_replace_existing_no_tx,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_no_tx,
            max_error_sample=10,
            # 保持既有语义：即使 UNCHANGED 也计入 update_count
            process_unchanged=True,
            # route 原实现会按行捕获 AppError 并继续；这里保持同语义
            continue_on_app_error=True,
        )

        out = stats.to_dict()
        out["total_rows"] = len(rows)
        return out

