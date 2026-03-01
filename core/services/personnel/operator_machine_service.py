from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OperatorMachine
from core.models.enums import YesNo
from core.services.common.enum_normalizers import normalize_skill_level
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.common.normalize import normalize_text
from data.repositories import MachineRepository, OperatorMachineRepository, OperatorRepository


class OperatorMachineService:
    """人员-设备关联服务（OperatorMachine）。"""

    SKILL_LEVELS = ("beginner", "normal", "expert")
    SKILL_LEVEL_ZH = {"beginner": "初级", "normal": "普通", "expert": "熟练"}

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)
        self.repo = OperatorMachineRepository(conn, logger=logger)

    # 校验与工具方法
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @classmethod
    def _normalize_skill_level_optional(cls, value: Any) -> Optional[str]:
        """规范化技能等级（可选列；空/缺失返回 None）。"""
        try:
            return normalize_skill_level(value, default="normal", allow_none=True)
        except Exception as e:
            raise ValidationError("“技能等级”不合法（允许：beginner/normal/expert 或 中文：初级/普通/熟练）", field="技能等级") from e

    @staticmethod
    def _normalize_yes_no_optional(value: Any, field: str) -> Optional[str]:
        """规范化 yes/no（可选列；空/缺失返回 None）。"""
        if value is None:
            return None
        s = str(value).strip()
        if s == "":
            return None
        low = s.lower()
        if low in ("yes", "y", "true", "1", "on") or s in ("是", "主操", "主"):
            return YesNo.YES.value
        if low in ("no", "n", "false", "0", "off") or s in ("否", "非主操", "非主"):
            return YesNo.NO.value
        raise ValidationError("“主操设备”不合法（允许：yes/no 或 是/否）", field=field)

    def _ensure_operator_exists(self, operator_id: str) -> None:
        if not self.operator_repo.exists(operator_id):
            raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{operator_id}”不存在")

    def _ensure_machine_exists(self, machine_id: str) -> None:
        if not self.machine_repo.get(machine_id):
            raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{machine_id}”不存在")

    @staticmethod
    def _detect_optional_columns(rows: List[Dict[str, Any]]) -> Tuple[bool, bool]:
        has_skill_col = any(("技能等级" in (r or {})) or ("skill_level" in (r or {})) for r in (rows or []))
        has_primary_col = any(("主操设备" in (r or {})) or ("is_primary" in (r or {})) for r in (rows or []))
        return bool(has_skill_col), bool(has_primary_col)

    @staticmethod
    def _detect_optional_columns_from_preview(preview_rows: List[ImportPreviewRow]) -> Tuple[bool, bool]:
        has_skill_col = any(("技能等级" in (pr.data or {})) or ("skill_level" in (pr.data or {})) for pr in (preview_rows or []))
        has_primary_col = any(("主操设备" in (pr.data or {})) or ("is_primary" in (pr.data or {})) for pr in (preview_rows or []))
        return bool(has_skill_col), bool(has_primary_col)

    def _build_existing_link_map(self) -> Dict[str, Dict[str, str]]:
        existing_links = self.repo.list_simple_rows()
        existing_map: Dict[str, Dict[str, str]] = {}
        for r in existing_links or []:
            op_id = str(r.get("operator_id") or "").strip()
            mc_id = str(r.get("machine_id") or "").strip()
            if not op_id or not mc_id:
                continue
            existing_map[f"{op_id}|{mc_id}"] = {
                "skill_level": str(r.get("skill_level") or "normal"),
                "is_primary": str(r.get("is_primary") or YesNo.NO.value),
            }
        return existing_map

    def _validate_required_ids_for_preview_row(self, row: Dict[str, Any], row_num: int) -> Tuple[Optional[str], Optional[str], Optional[ImportPreviewRow]]:
        op_id = self._normalize_text((row or {}).get("工号"))
        if not op_id:
            return None, None, ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“工号”不能为空")

        mc_id = self._normalize_text((row or {}).get("设备编号"))
        if not mc_id:
            return None, None, ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“设备编号”不能为空")

        row["工号"] = op_id
        row["设备编号"] = mc_id
        return op_id, mc_id, None

    @staticmethod
    def _check_duplicate_key_in_file(key: str, *, row: Dict[str, Any], row_num: int, seen_in_file: Set[str]) -> Optional[ImportPreviewRow]:
        if key in seen_in_file:
            return ImportPreviewRow(
                row_num=row_num,
                status=RowStatus.ERROR,
                data=row,
                message="Excel 中存在重复的“工号+设备编号”行，请去重后再导入。",
            )
        seen_in_file.add(key)
        return None

    def _check_fk_exists(self, op_id: str, mc_id: str, *, row: Dict[str, Any], row_num: int) -> Optional[ImportPreviewRow]:
        if not self.operator_repo.exists(op_id):
            return ImportPreviewRow(
                row_num=row_num,
                status=RowStatus.ERROR,
                data=row,
                message=f"人员“{op_id}”不存在，请先在人员管理中新增该人员。",
            )
        if not self.machine_repo.get(mc_id):
            return ImportPreviewRow(
                row_num=row_num,
                status=RowStatus.ERROR,
                data=row,
                message=f"设备“{mc_id}”不存在，请先在设备管理中新增该设备。",
            )
        return None

    def _parse_skill_optional_for_preview(self, row: Dict[str, Any], row_num: int, *, has_skill_col: bool) -> Tuple[Optional[str], Optional[ImportPreviewRow]]:
        if not has_skill_col:
            return None, None
        skill_raw = row.get("技能等级") if "技能等级" in row else row.get("skill_level")
        try:
            skill_norm = self._normalize_skill_level_optional(skill_raw)
            if skill_norm is not None:
                row["技能等级"] = skill_norm
            return skill_norm, None
        except Exception as e:
            msg = e.message if isinstance(e, ValidationError) else str(e)
            return None, ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message=msg)

    def _parse_primary_optional_for_preview(self, row: Dict[str, Any], row_num: int, *, has_primary_col: bool) -> Tuple[Optional[str], Optional[ImportPreviewRow]]:
        if not has_primary_col:
            return None, None
        primary_raw = row.get("主操设备") if "主操设备" in row else row.get("is_primary")
        try:
            primary_norm = self._normalize_yes_no_optional(primary_raw, field="主操设备")
            if primary_norm is not None:
                row["主操设备"] = primary_norm
            return primary_norm, None
        except Exception as e:
            msg = e.message if isinstance(e, ValidationError) else str(e)
            return None, ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message=msg)

    def _build_overwrite_preview_for_existing(self, *, row: Dict[str, Any], row_num: int, key: str, existing_map: Dict[str, Dict[str, str]], has_skill_col: bool, has_primary_col: bool, skill_norm: Optional[str], primary_norm: Optional[str]) -> ImportPreviewRow:
        old = existing_map.get(key) or {"skill_level": "normal", "is_primary": YesNo.NO.value}
        new_skill = old["skill_level"] if skill_norm is None else skill_norm
        new_primary = old["is_primary"] if primary_norm is None else primary_norm
        changes: Dict[str, Tuple[Any, Any]] = {}
        if has_skill_col and skill_norm is not None and new_skill != old["skill_level"]:
            changes["技能等级"] = (old["skill_level"], new_skill)
        if has_primary_col and primary_norm is not None and new_primary != old["is_primary"]:
            changes["主操设备"] = (old["is_primary"], new_primary)

        if changes:
            return ImportPreviewRow(row_num=row_num, status=RowStatus.UPDATE, data=row, message="将更新关联字段", changes=changes)
        return ImportPreviewRow(row_num=row_num, status=RowStatus.UNCHANGED, data=row, message="已存在（无变更）")

    def _decide_preview_row(self, *, row: Dict[str, Any], row_num: int, mode: ImportMode, key: str, existing_map: Dict[str, Dict[str, str]], has_skill_col: bool, has_primary_col: bool, skill_norm: Optional[str], primary_norm: Optional[str]) -> ImportPreviewRow:
        exists = key in existing_map
        if mode == ImportMode.REPLACE:
            return ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="替换模式：将写入关联")
        if not exists:
            return ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="新增关联")
        if mode == ImportMode.APPEND:
            return ImportPreviewRow(row_num=row_num, status=RowStatus.SKIP, data=row, message="已存在，按“追加”模式将跳过")
        if not has_skill_col and not has_primary_col:
            return ImportPreviewRow(row_num=row_num, status=RowStatus.UNCHANGED, data=row, message="已存在（覆盖模式下保持不变）")
        return self._build_overwrite_preview_for_existing(row=row, row_num=row_num, key=key, existing_map=existing_map, has_skill_col=has_skill_col, has_primary_col=has_primary_col, skill_norm=skill_norm, primary_norm=primary_norm)

    def _preview_one_row(self, *, row: Dict[str, Any], row_num: int, mode: ImportMode, has_skill_col: bool, has_primary_col: bool, existing_map: Dict[str, Dict[str, str]], seen_in_file: Set[str]) -> ImportPreviewRow:
        op_id, mc_id, err = self._validate_required_ids_for_preview_row(row, row_num)
        if err is not None:
            return err
        if op_id is None or mc_id is None:
            return ImportPreviewRow(
                row_num=row_num,
                status=RowStatus.ERROR,
                data=row,
                message="内部解析异常：工号/设备编号意外为空",
            )

        key = f"{op_id}|{mc_id}"
        dup = self._check_duplicate_key_in_file(key, row=row, row_num=row_num, seen_in_file=seen_in_file)
        if dup is not None:
            return dup

        fk_err = self._check_fk_exists(op_id, mc_id, row=row, row_num=row_num)
        if fk_err is not None:
            return fk_err

        skill_norm, skill_err = self._parse_skill_optional_for_preview(row, row_num, has_skill_col=has_skill_col)
        if skill_err is not None:
            return skill_err
        primary_norm, prim_err = self._parse_primary_optional_for_preview(row, row_num, has_primary_col=has_primary_col)
        if prim_err is not None:
            return prim_err

        return self._decide_preview_row(row=row, row_num=row_num, mode=mode, key=key, existing_map=existing_map, has_skill_col=has_skill_col, has_primary_col=has_primary_col, skill_norm=skill_norm, primary_norm=primary_norm)

    @staticmethod
    def _is_primary_yes(data: Dict[str, Any]) -> bool:
        v = str((data or {}).get("主操设备") or (data or {}).get("is_primary") or "").strip().lower()
        return v == YesNo.YES.value

    def _collect_dup_primary_yes_operators(self, preview: List[ImportPreviewRow]) -> Set[str]:
        counts: Dict[str, int] = {}
        for pr in preview or []:
            if pr.status == RowStatus.ERROR:
                continue
            op_id = self._normalize_text((pr.data or {}).get("工号")) or ""
            if not op_id:
                continue
            if self._is_primary_yes(pr.data or {}):
                counts[op_id] = int(counts.get(op_id, 0)) + 1
        return {op_id for op_id, cnt in counts.items() if int(cnt) > 1}

    @staticmethod
    def _mark_dup_primary_yes(preview: List[ImportPreviewRow], dup_ops: Set[str]) -> None:
        for pr in preview or []:
            if pr.status == RowStatus.ERROR:
                continue
            op_id = str((pr.data or {}).get("工号") or "").strip()
            if not op_id:
                continue
            if op_id in dup_ops and OperatorMachineService._is_primary_yes(pr.data or {}):
                pr.status = RowStatus.ERROR
                pr.message = f"人员“{op_id}”在 Excel 中设置了多个主操设备（主操设备=yes 只能有一条）。"
                pr.changes = {}

    def _enforce_primary_unique_in_file(self, preview: List[ImportPreviewRow]) -> None:
        dup_ops = self._collect_dup_primary_yes_operators(preview)
        if dup_ops:
            self._mark_dup_primary_yes(preview, dup_ops)

    def _resolve_write_values(
        self,
        pr: ImportPreviewRow,
        *,
        has_skill_col: bool,
        has_primary_col: bool,
        old: Optional[Dict[str, str]],
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        data = pr.data or {}
        skill_raw = data.get("技能等级") if "技能等级" in data else data.get("skill_level")
        primary_raw = data.get("主操设备") if "主操设备" in data else data.get("is_primary")

        try:
            skill_norm = self._normalize_skill_level_optional(skill_raw) if has_skill_col else None
            primary_norm = self._normalize_yes_no_optional(primary_raw, field="主操设备") if has_primary_col else None
        except Exception as e:
            msg = e.message if isinstance(e, ValidationError) else str(e)
            return None, None, msg

        base_skill = (old.get("skill_level") if old else None) or "normal"
        base_primary = (old.get("is_primary") if old else None) or YesNo.NO.value
        new_skill = base_skill if skill_norm is None else skill_norm
        new_primary = base_primary if primary_norm is None else primary_norm
        return str(new_skill), str(new_primary), None

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

        # 规范化可选字段
        skill_norm = self._normalize_skill_level_optional(skill_level) or "normal"
        primary_norm = self._normalize_yes_no_optional(is_primary, field="主操设备") or YesNo.NO.value

        with self.tx_manager.transaction():
            if primary_norm == YesNo.YES.value:
                # 主操设备约束：同一人员仅允许 1 台主操设备
                self.repo.clear_primary_for_operator(op_id)
            return self.repo.add(op_id, mc_id, skill_level=skill_norm, is_primary=primary_norm)

    def remove_link(self, operator_id: Any, machine_id: Any) -> None:
        op_id = self._normalize_text(operator_id)
        mc_id = self._normalize_text(machine_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        with self.tx_manager.transaction():
            self.repo.remove(op_id, mc_id)

    def update_link_fields(
        self,
        operator_id: Any,
        machine_id: Any,
        *,
        skill_level: Any,
        is_primary: Any,
    ) -> None:
        """
        更新关联字段（技能等级/主操设备）。

        约束：
        - skill_level 允许：beginner/normal/expert（兼容中文）
        - is_primary：yes/no
        - 同一人员仅允许 1 台主操设备（is_primary=yes 会自动清空该人员其它关联的主操标记）
        """
        op_id = self._normalize_text(operator_id)
        mc_id = self._normalize_text(machine_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        if not self.repo.exists(op_id, mc_id):
            raise BusinessError(ErrorCode.NOT_FOUND, "未找到该人员与该设备的关联记录。")

        skill_norm = self._normalize_skill_level_optional(skill_level) or "normal"
        primary_norm = self._normalize_yes_no_optional(is_primary, field="主操设备") or YesNo.NO.value

        with self.tx_manager.transaction():
            if primary_norm == YesNo.YES.value:
                self.repo.clear_primary_for_operator(op_id)
            self.repo.update_fields(op_id, mc_id, skill_level=skill_norm, is_primary=primary_norm)

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
        has_skill_col, has_primary_col = self._detect_optional_columns(rows)
        existing_map = self._build_existing_link_map()

        preview: List[ImportPreviewRow] = []
        seen_in_file: Set[str] = set()

        for idx, row in enumerate(rows or []):
            row_num = idx + 2
            pr = self._preview_one_row(
                row=row or {},
                row_num=row_num,
                mode=mode,
                has_skill_col=has_skill_col,
                has_primary_col=has_primary_col,
                existing_map=existing_map,
                seen_in_file=seen_in_file,
            )
            preview.append(pr)

        if has_primary_col:
            self._enforce_primary_unique_in_file(preview)

        return preview

    def apply_import_links(self, preview_rows: List[ImportPreviewRow], mode: ImportMode) -> Dict[str, Any]:
        """
        按预览结果落库（忽略 ERROR 行），返回统计字段（用于页面提示与留痕）。
        """
        new_count = update_count = skip_count = error_count = 0
        errors_sample: List[Dict[str, Any]] = []

        has_skill_col, has_primary_col = self._detect_optional_columns_from_preview(preview_rows)
        existing_map = self._build_existing_link_map()

        with self.tx_manager.transaction():
            if mode == ImportMode.REPLACE:
                self.repo.delete_all()
                existing_map = {}

            for pr in preview_rows or []:
                if pr.status == RowStatus.ERROR:
                    error_count += 1
                    if pr.message and len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": pr.message})
                    continue

                if pr.status == RowStatus.SKIP:
                    skip_count += 1
                    continue

                if pr.status == RowStatus.UNCHANGED:
                    skip_count += 1
                    continue

                op_id = str(pr.data.get("工号") or "").strip()
                mc_id = str(pr.data.get("设备编号") or "").strip()
                if not op_id or not mc_id:
                    error_count += 1
                    if len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": "缺少“工号/设备编号”，无法写入。"})
                    continue

                key = f"{op_id}|{mc_id}"
                old = existing_map.get(key)

                new_skill, new_primary, err = self._resolve_write_values(
                    pr, has_skill_col=has_skill_col, has_primary_col=has_primary_col, old=old
                )
                if err:
                    error_count += 1
                    if len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": err})
                    continue

                # 写入
                if self.repo.exists(op_id, mc_id):
                    if mode == ImportMode.APPEND:
                        skip_count += 1
                        continue
                    # 更新
                    if new_primary == YesNo.YES.value:
                        self.repo.clear_primary_for_operator(op_id)
                    self.repo.update_fields(op_id, mc_id, skill_level=new_skill, is_primary=new_primary)
                    update_count += 1
                    existing_map[key] = {"skill_level": new_skill, "is_primary": new_primary}
                else:
                    if new_primary == YesNo.YES.value:
                        self.repo.clear_primary_for_operator(op_id)
                    self.repo.add(op_id, mc_id, skill_level=new_skill, is_primary=new_primary)
                    new_count += 1
                    existing_map[key] = {"skill_level": new_skill, "is_primary": new_primary}

        return {
            "total_rows": len(preview_rows),
            "new_count": new_count,
            "update_count": update_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors_sample": errors_sample,
        }

