from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.models.enums import OPERATOR_STATUS_VALUES
from core.services.common.enum_normalizers import normalize_operator_status
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.common.normalize import normalize_text, to_str_or_blank
from core.services.personnel.operator_service import OperatorService
from core.services.personnel.resource_team_service import ResourceTeamService
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
        self.team_svc = ResourceTeamService(conn, logger=logger, op_logger=op_logger)
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
            return to_str_or_blank((getattr(pr, "data", None) or {}).get("工号"))

        def _apply_row_no_tx(pr: Any, existed: bool) -> None:
            data = getattr(pr, "data", None) or {}
            op_id = to_str_or_blank(data.get("工号"))
            if not op_id:
                raise ValidationError("工号不能为空", field="工号")
            name = normalize_text(data.get("姓名"))
            if not name:
                raise ValidationError("姓名不能为空", field="姓名")
            status = normalize_operator_status(data.get("状态"))
            if not status:
                raise ValidationError("状态不能为空，请填写：在岗 或 停用。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。", field="状态")
            if status not in OPERATOR_STATUS_VALUES:
                raise ValidationError("状态不合法，可填写：在岗 / 停用。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。", field="状态")
            remark = normalize_text(data.get("备注"))
            team_in_payload = "班组" in data
            team_id = self.team_svc.resolve_team_id_optional(data.get("班组")) if team_in_payload else None
            if existed:
                payload: Dict[str, Any] = {"name": name, "status": status, "remark": remark}
                if team_in_payload:
                    payload["team_id"] = team_id
                self.repo.update(op_id, payload)
            else:
                payload = {"operator_id": op_id, "name": name, "status": status, "remark": remark}
                if team_in_payload:
                    payload["team_id"] = team_id
                self.repo.create(payload)

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
            continue_on_app_error=False,
        )

        out = stats.to_dict()
        out["total_rows"] = len(rows)
        return out
