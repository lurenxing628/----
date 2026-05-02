from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.models.enums import SOURCE_TYPE_VALUES
from core.services.common.enum_normalizers import normalize_op_type_category
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.common.normalize import to_str_or_blank
from core.services.process.op_type_service import OpTypeService
from data.repositories import OpTypeRepository


class OpTypeExcelImportService:
    """
    工种配置（OpTypes）Excel 导入落库服务。

    说明：
    - Route 层负责：文件读取、预览、用户确认
    - 本服务负责：按预览结果写库（避免 Route 直接依赖 Repository）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.svc = OpTypeService(conn, logger=logger, op_logger=op_logger)
        self.repo = OpTypeRepository(conn, logger=logger)

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
            return to_str_or_blank((getattr(pr, "data", None) or {}).get("工种ID"))

        def _apply_row_no_tx(pr: Any, existed: bool) -> None:
            data = getattr(pr, "data", None) or {}
            ot_id = to_str_or_blank(data.get("工种ID"))
            if not ot_id:
                raise ValidationError("“工种编号（模板列名：工种ID）”不能为空", field="工种ID")
            name = to_str_or_blank(data.get("工种名称"))
            if not name:
                raise ValidationError("“工种名称”不能为空", field="工种名称")

            cat = normalize_op_type_category(data.get("归属"))
            if cat not in SOURCE_TYPE_VALUES:
                raise ValidationError("“归属”不合法，请填写“自制”或“外协”。如果以前的文件写过旧叫法，系统会尽量按自制或外协读取；新文件请直接写“自制”或“外协”。", field="归属")
            if existed:
                self.svc.update(ot_id, name=name, category=cat)
            else:
                self.svc.create(ot_id, name, category=cat)

        stats = execute_preview_rows_transactional(
            self.conn,
            mode=mode,
            preview_rows=rows,
            existing_row_ids=existing_row_ids,
            replace_existing_no_tx=_replace_existing_no_tx,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_no_tx,
            max_error_sample=10,
            process_unchanged=False,
            # route 原实现会按行捕获 AppError 并继续；这里保持同语义
            continue_on_app_error=True,
        )

        out = stats.to_dict()
        out["total_rows"] = len(rows)
        return out
