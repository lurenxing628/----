from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OperatorMachine
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

    # -------------------------
    # 校验与工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @classmethod
    def _normalize_skill_level_optional(cls, value: Any) -> Optional[str]:
        """
        规范化技能等级（可选列）：
        - 为空/缺失：返回 None（表示“不修改/按默认”）
        - 允许：beginner/normal/expert（兼容常见中文）
        """
        if value is None:
            return None
        s = str(value).strip()
        if s == "":
            return None
        low = s.lower()
        zh_map = {
            "初级": "beginner",
            "新手": "beginner",
            "普通": "normal",
            "一般": "normal",
            "中级": "normal",
            "熟练": "expert",
            "高级": "expert",
            "专家": "expert",
        }
        if low in cls.SKILL_LEVELS:
            return low
        if s in zh_map:
            return zh_map[s]
        raise ValidationError("“技能等级”不合法（允许：beginner/normal/expert 或 中文：初级/普通/熟练）", field="技能等级")

    @staticmethod
    def _normalize_yes_no_optional(value: Any, field: str) -> Optional[str]:
        """
        规范化 yes/no（可选列）：
        - 为空/缺失：返回 None（表示“不修改/按默认”）
        """
        if value is None:
            return None
        s = str(value).strip()
        if s == "":
            return None
        low = s.lower()
        if low in ("yes", "y", "true", "1", "on") or s in ("是", "主操", "主"):
            return "yes"
        if low in ("no", "n", "false", "0", "off") or s in ("否", "非主操", "非主"):
            return "no"
        raise ValidationError("“主操设备”不合法（允许：yes/no 或 是/否）", field=field)

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

        # 规范化可选字段
        skill_norm = self._normalize_skill_level_optional(skill_level) or "normal"
        primary_norm = self._normalize_yes_no_optional(is_primary, field="主操设备") or "no"

        with self.tx_manager.transaction():
            if primary_norm == "yes":
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
        primary_norm = self._normalize_yes_no_optional(is_primary, field="主操设备") or "no"

        with self.tx_manager.transaction():
            if primary_norm == "yes":
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
        preview: List[ImportPreviewRow] = []

        # 是否包含可选列（存在任意一行含该列名则认为用户要维护）
        has_skill_col = any(("技能等级" in r) or ("skill_level" in r) for r in rows)
        has_primary_col = any(("主操设备" in r) or ("is_primary" in r) for r in rows)

        # 现有关联（含可选字段）
        existing_links = self.conn.execute(
            "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine"
        ).fetchall()
        existing_map: Dict[str, Dict[str, str]] = {
            f"{r['operator_id']}|{r['machine_id']}": {
                "skill_level": str(r["skill_level"] or "normal"),
                "is_primary": str(r["is_primary"] or "no"),
            }
            for r in existing_links
        }

        seen_in_file: Set[str] = set()
        primary_yes_by_operator: Dict[str, List[int]] = {}

        for idx, row in enumerate(rows):
            row_num = idx + 2
            op_id = self._normalize_text(row.get("工号"))
            mc_id = self._normalize_text(row.get("设备编号"))

            if not op_id:
                preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“工号”不能为空"))
                continue
            if not mc_id:
                preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message="“设备编号”不能为空"))
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

            # 可选列解析（不强制）：用于 UPDATE/写入
            skill_norm: Optional[str] = None
            primary_norm: Optional[str] = None
            if has_skill_col:
                try:
                    skill_norm = self._normalize_skill_level_optional(row.get("技能等级") if "技能等级" in row else row.get("skill_level"))
                    if skill_norm is not None:
                        row["技能等级"] = skill_norm
                except Exception as e:
                    msg = e.message if isinstance(e, ValidationError) else str(e)
                    preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message=msg))
                    continue
            if has_primary_col:
                try:
                    primary_norm = self._normalize_yes_no_optional(row.get("主操设备") if "主操设备" in row else row.get("is_primary"), field="主操设备")
                    if primary_norm is not None:
                        row["主操设备"] = primary_norm
                except Exception as e:
                    msg = e.message if isinstance(e, ValidationError) else str(e)
                    preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.ERROR, data=row, message=msg))
                    continue

            if has_primary_col and primary_norm == "yes":
                primary_yes_by_operator.setdefault(op_id, []).append(len(preview))

            exists = key in existing_map

            if mode == ImportMode.REPLACE:
                preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="替换模式：将写入关联"))
                continue

            if exists:
                if mode == ImportMode.APPEND:
                    preview.append(
                        ImportPreviewRow(row_num=row_num, status=RowStatus.SKIP, data=row, message="已存在，按“追加”模式将跳过")
                    )
                    continue

                # OVERWRITE：若未提供可选列，则保持不变；提供则按差异决定 UPDATE/UNCHANGED
                if not has_skill_col and not has_primary_col:
                    preview.append(
                        ImportPreviewRow(row_num=row_num, status=RowStatus.UNCHANGED, data=row, message="已存在（覆盖模式下保持不变）")
                    )
                    continue

                old = existing_map.get(key) or {"skill_level": "normal", "is_primary": "no"}
                new_skill = old["skill_level"] if skill_norm is None else skill_norm
                new_primary = old["is_primary"] if primary_norm is None else primary_norm
                changes: Dict[str, Tuple[Any, Any]] = {}
                if has_skill_col and skill_norm is not None and new_skill != old["skill_level"]:
                    changes["技能等级"] = (old["skill_level"], new_skill)
                if has_primary_col and primary_norm is not None and new_primary != old["is_primary"]:
                    changes["主操设备"] = (old["is_primary"], new_primary)

                if changes:
                    preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.UPDATE, data=row, message="将更新关联字段", changes=changes))
                else:
                    preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.UNCHANGED, data=row, message="已存在（无变更）"))
            else:
                preview.append(ImportPreviewRow(row_num=row_num, status=RowStatus.NEW, data=row, message="新增关联"))

        # 主操设备约束：同一人员在 Excel 中显式设置 is_primary=yes 只能出现 1 次
        if has_primary_col:
            dup_ops = {op_id for op_id, idxs in primary_yes_by_operator.items() if len(idxs) > 1}
            if dup_ops:
                for pr in preview:
                    if pr.status == RowStatus.ERROR:
                        continue
                    op_id = self._normalize_text(pr.data.get("工号")) or ""
                    prim = None
                    try:
                        prim = self._normalize_yes_no_optional(pr.data.get("主操设备") or pr.data.get("is_primary"), field="主操设备")
                    except Exception:
                        prim = None
                    if op_id in dup_ops and prim == "yes":
                        pr.status = RowStatus.ERROR
                        pr.message = f"人员“{op_id}”在 Excel 中设置了多个主操设备（主操设备=yes 只能有一条）。"
                        pr.changes = {}

        return preview

    def apply_import_links(self, preview_rows: List[ImportPreviewRow], mode: ImportMode) -> Dict[str, Any]:
        """
        按预览结果落库（忽略 ERROR 行），返回统计字段（用于页面提示与留痕）。
        """
        new_count = update_count = skip_count = error_count = 0
        errors_sample: List[Dict[str, Any]] = []

        # 是否包含可选列
        has_skill_col = any(("技能等级" in (pr.data or {})) or ("skill_level" in (pr.data or {})) for pr in preview_rows)
        has_primary_col = any(("主操设备" in (pr.data or {})) or ("is_primary" in (pr.data or {})) for pr in preview_rows)

        # 现有值（用于 OVERWRITE 的“空值=不修改”语义）
        existing_links = self.conn.execute(
            "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine"
        ).fetchall()
        existing_map: Dict[str, Dict[str, str]] = {
            f"{r['operator_id']}|{r['machine_id']}": {
                "skill_level": str(r["skill_level"] or "normal"),
                "is_primary": str(r["is_primary"] or "no"),
            }
            for r in existing_links
        }

        with self.tx_manager.transaction():
            if mode == ImportMode.REPLACE:
                self.conn.execute("DELETE FROM OperatorMachine")
                existing_map = {}

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

                # 解析新值（空=不修改/按默认）
                skill_raw = pr.data.get("技能等级") if "技能等级" in pr.data else pr.data.get("skill_level")
                primary_raw = pr.data.get("主操设备") if "主操设备" in pr.data else pr.data.get("is_primary")

                skill_norm = None
                primary_norm = None
                try:
                    if has_skill_col:
                        skill_norm = self._normalize_skill_level_optional(skill_raw)
                    if has_primary_col:
                        primary_norm = self._normalize_yes_no_optional(primary_raw, field="主操设备")
                except Exception as e:
                    msg = e.message if isinstance(e, ValidationError) else str(e)
                    error_count += 1
                    if len(errors_sample) < 10:
                        errors_sample.append({"row": pr.row_num, "message": msg})
                    continue

                new_skill = (old["skill_level"] if old else "normal") if skill_norm is None else skill_norm
                new_primary = (old["is_primary"] if old else "no") if primary_norm is None else primary_norm

                # 写入
                if self.repo.exists(op_id, mc_id):
                    if mode == ImportMode.APPEND:
                        skip_count += 1
                        continue
                    # 更新
                    if new_primary == "yes":
                        self.repo.clear_primary_for_operator(op_id)
                    self.repo.update_fields(op_id, mc_id, skill_level=new_skill, is_primary=new_primary)
                    update_count += 1
                    existing_map[key] = {"skill_level": new_skill, "is_primary": new_primary}
                else:
                    if new_primary == "yes":
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

