from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.personnel.operator_service import OperatorService
from data.repositories import OperatorRepository


class OperatorExcelImportService:
    """
    人员基本信息（Operators）Excel 导入落库服务。

    说明：
    - Route 层负责：文件读取、预览、用户确认
    - 本服务负责：按预览结果写库（避免 Route 直接依赖 Repository）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.svc = OperatorService(conn, logger=logger, op_logger=op_logger)
        self.repo = OperatorRepository(conn, logger=logger)

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
            return str((getattr(pr, "data", None) or {}).get("工号") or "").strip()

        def _apply_row_no_tx(pr: Any, existed: bool) -> None:
            data = getattr(pr, "data", None) or {}
            op_id = str(data.get("工号") or "").strip()
            if not op_id:
                raise ValidationError("“工号”不能为空", field="工号")
            name = data.get("姓名")
            if name is None or str(name).strip() == "":
                raise ValidationError("“姓名”不能为空", field="姓名")
            status = ("" if data.get("状态") is None else str(data.get("状态"))).strip()
            if not status:
                raise ValidationError("“状态”不能为空（允许：active / inactive）", field="状态")
            if status not in ("active", "inactive"):
                raise ValidationError("“状态”不合法（允许：active / inactive）", field="状态")
            remark = data.get("备注")
            if existed:
                self.repo.update(op_id, {"name": name, "status": status, "remark": remark})
            else:
                self.repo.create({"operator_id": op_id, "name": name, "status": status, "remark": remark})

        stats = execute_preview_rows_transactional(
            self.conn,
            mode=mode,
            preview_rows=rows,
            existing_row_ids=existing_row_ids,
            replace_existing_no_tx=_replace_existing_no_tx,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_no_tx,
            max_error_sample=10,
            # 保持既有语义：即使 UNCHANGED 也会更新 updated_at，并计入 update_count
            process_unchanged=True,
            continue_on_app_error=False,
        )

        out = stats.to_dict()
        out["total_rows"] = len(rows)
        return out

