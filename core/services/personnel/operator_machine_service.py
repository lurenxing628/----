from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.models import OperatorMachine
from data.repositories import MachineRepository, OperatorMachineRepository, OperatorRepository


class OperatorMachineService:
    """人员-设备关联服务（OperatorMachine）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)
        self.repo = OperatorMachineRepository(conn, logger=logger)

    # -------------------------
    # 校验与工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    def _ensure_operator_exists(self, operator_id: str) -> None:
        if not self.operator_repo.exists(operator_id):
            raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{operator_id}”不存在")

    def _ensure_machine_exists(self, machine_id: str) -> None:
        if not self.machine_repo.get(machine_id):
            raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{machine_id}”不存在")

    # -------------------------
    # 关联 CRUD
    # -------------------------
    def list_by_operator(self, operator_id: str) -> List[OperatorMachine]:
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        return self.repo.list_by_operator(op_id)

    def list_by_machine(self, machine_id: str) -> List[OperatorMachine]:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        return self.repo.list_by_machine(mc_id)

    def add_link(
        self,
        operator_id: Any,
        machine_id: Any,
        skill_level: str = "normal",
        is_primary: str = "no",
    ) -> OperatorMachine:
        op_id = self._normalize_text(operator_id)
        mc_id = self._normalize_text(machine_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")

        self._ensure_operator_exists(op_id)
        self._ensure_machine_exists(mc_id)

        if self.repo.exists(op_id, mc_id):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "该人员与该设备已有关联，无需重复添加。")

        with self.tx_manager.transaction():
            return self.repo.add(op_id, mc_id, skill_level=skill_level, is_primary=is_primary)

    def remove_link(self, operator_id: Any, machine_id: Any) -> None:
        op_id = self._normalize_text(operator_id)
        mc_id = self._normalize_text(machine_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        with self.tx_manager.transaction():
            self.repo.remove(op_id, mc_id)

    # -------------------------
    # Excel 导入预览（复合键：工号|设备编号）
    # -------------------------
    def preview_import_links(
        self,
        rows: List[Dict[str, Any]],
        mode: ImportMode = ImportMode.OVERWRITE,
    ) -> List[ImportPreviewRow]:
        """
        输入 rows 的键名为中文列名：
        - 工号
        - 设备编号
        """
        preview: List[ImportPreviewRow] = []

        # 现有关联集合
        existing_links = self.conn.execute("SELECT operator_id, machine_id FROM OperatorMachine").fetchall()
        existing_keys: Set[str] = {f"{r['operator_id']}|{r['machine_id']}" for r in existing_links}

        seen_in_file: Set[str] = set()
        for idx, row in enumerate(rows):
            row_num = idx + 2
            op_id = self._normalize_text(row.get("工号"))
            mc_id = self._normalize_text(row.get("设备编号"))

            if not op_id:
                preview.append(
                    ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“工号”不能为空")
                )
                continue
            if not mc_id:
                preview.append(
                    ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“设备编号”不能为空")
                )
                continue

            # 标准化写回（确保后续落库一致）
            row["工号"] = op_id
            row["设备编号"] = mc_id
            key = f"{op_id}|{mc_id}"

            if key in seen_in_file:
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.ERROR,
                        data=row,
                        message="Excel 中存在重复的“工号+设备编号”行，请去重后再导入。",
                    )
                )
                continue
            seen_in_file.add(key)

            # 引用存在性校验（用户提示中文，避免 FK 英文报错）
            if not self.operator_repo.exists(op_id):
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.ERROR,
                        data=row,
                        message=f"人员“{op_id}”不存在，请先在人员管理中新增该人员。",
                    )
                )
                continue
            if not self.machine_repo.get(mc_id):
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.ERROR,
                        data=row,
                        message=f"设备“{mc_id}”不存在，请先在设备管理中新增该设备。",
                    )
                )
                continue

            exists = key in existing_keys

            if mode == ImportMode.REPLACE:
                # 替换模式会清空后再导入，因此全部按 NEW 预览更直观
                preview.append(
                    ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="替换模式：将写入关联")
                )
                continue

            if exists:
                if mode == ImportMode.APPEND:
                    preview.append(
                        ImportPreviewRow(row_num=row_num, status=RowStatus.SKIP, data=row, message="已存在，按“追加”模式将跳过")
                    )
                else:
                    # 覆盖模式下，关联表无可更新字段（暂不在 Excel 中维护 skill_level/is_primary）
                    preview.append(
                        ImportPreviewRow(row_num=row_num, status=RowStatus.UNCHANGED, data=row, message="已存在（覆盖模式下保持不变）")
                    )
            else:
                preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="新增关联"))

        return preview

    def apply_import_links(self, preview_rows: List[ImportPreviewRow], mode: ImportMode) -> Dict[str, Any]:
        """
        按预览结果落库（忽略 ERROR 行），返回统计字段（用于页面提示与留痕）。
        """
        new_count = update_count = skip_count = error_count = 0
        errors_sample: List[Dict[str, Any]] = []

        with self.tx_manager.transaction():
            if mode == ImportMode.REPLACE:
                self.conn.execute("DELETE FROM OperatorMachine")

            for pr in preview_rows:
                if pr.status == RowStatus.ERROR:
                    error_count += 1
                    if pr.message and len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": pr.message})
                    continue

                if pr.status == RowStatus.SKIP:
                    skip_count += 1
                    continue

                if pr.status == RowStatus.UNCHANGED:
                    # 覆盖模式：不更新任何字段
                    continue

                # NEW（以及 REPLACE 下的 NEW）
                op_id = str(pr.data.get("工号") or "").strip()
                mc_id = str(pr.data.get("设备编号") or "").strip()
                if not op_id or not mc_id:
                    # 理论上不会发生，但防御一下
                    error_count += 1
                    if len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": "缺少“工号/设备编号”，无法写入。"})
                    continue

                # 避免重复写入导致 UNIQUE 报错：再次检查存在性
                if self.repo.exists(op_id, mc_id):
                    if mode == ImportMode.APPEND:
                        skip_count += 1
                        continue
                    continue

                self.repo.add(op_id, mc_id)
                new_count += 1

        return {
            "total_rows": len(preview_rows),
            "new_count": new_count,
            "update_count": update_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors_sample": errors_sample,
        }

