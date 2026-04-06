from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.models.enums import MACHINE_STATUS_VALUES
from core.services.common.enum_normalizers import normalize_machine_status
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.common.normalize import to_str_or_blank
from core.services.equipment.machine_service import MachineService
from core.services.personnel.resource_team_service import ResourceTeamService
from core.services.process.op_type_service import OpTypeService
from data.repositories import MachineRepository


class MachineExcelImportService:
    """
    设备 Excel 导入落库服务（含事务控制）。

    说明：
    - Route 层负责：文件读取、预览、用户确认
    - 本服务负责：按预览结果写库（保持原有语义，避免 Route 直接依赖 Repository）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger

        self.machine_svc = MachineService(conn, logger=logger, op_logger=op_logger)
        self.team_svc = ResourceTeamService(conn, logger=logger, op_logger=op_logger)
        self.op_type_svc = OpTypeService(conn, logger=logger, op_logger=op_logger)
        self.repo = MachineRepository(conn, logger=logger)

    @staticmethod
    def _normalize_machine_status_for_excel(value: Any) -> str:
        return normalize_machine_status(value)

    def _resolve_op_type_id_strict_for_excel(self, value: Any) -> Optional[str]:
        raw = to_str_or_blank(value)
        if not raw:
            return None
        op_type_id = self.op_type_svc.resolve_op_type_id_optional(raw)
        if not op_type_id:
            raise ValidationError(f"工种{raw}不存在，请先在工艺管理-工种配置中维护。", field="工种")
        return op_type_id

    def apply_preview_rows(
        self,
        preview_rows: List[Any],
        *,
        mode: ImportMode,
        existing_ids: Set[str],
    ) -> Dict[str, Any]:
        rows = list(preview_rows or [])
        existing_row_ids = set(existing_ids or set())

        def _replace_existing_no_tx() -> None:
            self.machine_svc.ensure_replace_allowed()
            self.repo.delete_all()

        def _row_id_getter(pr: Any) -> str:
            return to_str_or_blank((getattr(pr, "data", None) or {}).get("设备编号"))

        def _apply_row_no_tx(pr: Any, existed: bool) -> None:
            data = getattr(pr, "data", None) or {}
            machine_id = to_str_or_blank(data.get("设备编号"))
            if not machine_id:
                raise ValidationError("设备编号不能为空", field="设备编号")

            name = to_str_or_blank(data.get("设备名称"))
            if not name:
                raise ValidationError("设备名称不能为空", field="设备名称")

            status = self._normalize_machine_status_for_excel(data.get("状态"))
            if not status:
                raise ValidationError("状态不能为空，请填写：可用 / 停用 / 维修（也兼容 active / inactive / maintain）。", field="状态")
            if status not in MACHINE_STATUS_VALUES:
                raise ValidationError("状态不合法，可填写：可用 / 停用 / 维修（也兼容 active / inactive / maintain）。", field="状态")

            payload: Dict[str, Any] = {
                "name": name,
                "op_type_id": self._resolve_op_type_id_strict_for_excel(data.get("工种")),
                "status": status,
            }
            if "班组" in data:
                payload["team_id"] = self.team_svc.resolve_team_id_optional(data.get("班组"))
            if existed:
                self.repo.update(machine_id, payload)
            else:
                self.repo.create({"machine_id": machine_id, **payload})

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
