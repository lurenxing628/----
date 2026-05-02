from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Part
from core.models.enums import YESNO_VALUES, YesNo
from core.services.common.normalize import append_unique_text_messages, normalize_text
from core.services.common.safe_logging import safe_warning
from data.repositories import (
    ExternalGroupRepository,
    OpTypeRepository,
    PartOperationRepository,
    PartRepository,
    SupplierRepository,
)

from .deletion_validator import DeletionValidator
from .part_delete_guard import PartDeleteGuard
from .part_excel_adapter import build_existing_for_excel_routes
from .part_route_validation import (
    build_internal_hours_snapshot,
    build_route_parse_baseline_snapshot,
    coerce_external_default_days,
    operation_source_or_raise,
    save_template_no_tx,
)
from .route_parser import ParseResult, ParseStatus, RouteParser


class PartService:
    """零件与工艺模板服务（Parts/PartOperations/ExternalGroups）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.part_repo = PartRepository(conn, logger=logger)
        self.op_repo = PartOperationRepository(conn, logger=logger)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)
        self.op_type_repo = OpTypeRepository(conn, logger=logger)
        self.supplier_repo = SupplierRepository(conn, logger=logger)

        self.route_parser = RouteParser(self.op_type_repo, self.supplier_repo, logger=logger)
        self.deletion_validator = DeletionValidator()
        self.delete_guard = PartDeleteGuard(
            op_repo=self.op_repo,
            group_repo=self.group_repo,
            tx_manager=self.tx_manager,
            deletion_validator=self.deletion_validator,
        )

    # -------------------------
    # 工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else 0.0
        try:
            return float(value)
        except Exception as e:
            raise ValidationError(f"“{field}”必须是数字", field=field) from e

    def _get_or_raise(self, part_no: str) -> Part:
        p = self.part_repo.get(part_no)
        if not p:
            raise BusinessError(ErrorCode.PART_NOT_FOUND, f"零件“{part_no}”不存在")
        return p

    def _build_internal_hours_snapshot(self, part_no: str) -> Dict[int, Tuple[float, float]]:
        return build_internal_hours_snapshot(self.op_repo, part_no)

    def _coerce_external_default_days(
        self,
        op: Any,
        *,
        warnings: Optional[List[str]] = None,
    ) -> Tuple[float, bool]:
        return coerce_external_default_days(op, logger=self.logger, warnings=warnings)

    @staticmethod
    def _operation_source_or_raise(op: Any) -> str:
        return operation_source_or_raise(op)

    # -------------------------
    # Parts CRUD
    # -------------------------
    def list(self, route_parsed: Optional[str] = None) -> List[Part]:
        if route_parsed and route_parsed not in YESNO_VALUES:
            raise ValidationError("工艺路线解析状态不正确，请选择：是 / 否。", field="工艺路线解析状态")
        return self.part_repo.list(route_parsed=route_parsed)

    def build_route_parse_baseline_snapshot(
        self,
        *,
        part_nos: List[str],
        parts_cache: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        为批次 Excel 预览基线生成“自动补建工序”快照。

        设计约束：
        - 不在 Route 层复制 RouteParser 的工种/供应商判定规则；
        - 基线只保留会影响自动补建结果的解析事实；
        - route_raw 自身的变化由调用方单独快照，避免这里重复携带原始输入。
        """
        return build_route_parse_baseline_snapshot(
            part_nos=part_nos,
            parts_cache=parts_cache,
            list_parts=self.list,
            parse_route=lambda route_raw, part_no: self.parse(route_raw, part_no=part_no, strict_mode=False),
        )

    def get(self, part_no: str) -> Part:
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        return self._get_or_raise(pn)

    def create(
        self,
        part_no: Any,
        part_name: Any,
        route_raw: Any = None,
        remark: Any = None,
        *,
        strict_mode: bool = False,
        user_warnings: Optional[List[str]] = None,
    ) -> Part:
        pn = self._normalize_text(part_no)
        name = self._normalize_text(part_name)
        rr = None if route_raw is None else str(route_raw)
        rmk = self._normalize_text(remark)

        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        if not name:
            raise ValidationError("“名称”不能为空", field="名称")
        if self.part_repo.get(pn):
            raise BusinessError(ErrorCode.PART_ALREADY_EXISTS, f"图号“{pn}”已存在，不能重复添加。")

        parse_result: Optional[ParseResult] = None
        if rr and str(rr).strip() and strict_mode:
            parse_result = self._parse_route_or_raise(part_no=pn, route_raw=rr, strict_mode=True)

        with self.tx_manager.transaction():
            self.part_repo.create(
                {
                    "part_no": pn,
                    "part_name": name,
                    "route_raw": rr,
                    "route_parsed": YesNo.YES.value if parse_result is not None else YesNo.NO.value,
                    "remark": rmk,
                }
            )
            if parse_result is not None:
                self._save_template_no_tx(part_no=pn, parse_result=parse_result)

        # 如果填写了工艺路线字符串，则尝试自动解析（失败时仍保留零件）
        if rr and str(rr).strip() and not strict_mode:
            try:
                auto_parse_result = self.reparse_and_save(part_no=pn, route_raw=rr, strict_mode=False)
                append_unique_text_messages(user_warnings, getattr(auto_parse_result, "warnings", None))
            except (BusinessError, ValidationError) as exc:
                # 不阻断创建；错误在详情页可见
                detail = getattr(exc, "message", None) or str(exc)
                safe_warning(self.logger, f"零件“{pn}”工艺路线自动解析失败，已保留零件：{detail}")
                append_unique_text_messages(
                    user_warnings,
                    f"零件已创建，但工序模板未成功生成，请检查工艺路线并重新解析。原因：{detail}",
                )

        return self._get_or_raise(pn)

    def update(self, part_no: Any, part_name: Any = None, route_raw: Any = None, remark: Any = None) -> Part:
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        self._get_or_raise(pn)

        updates: Dict[str, Any] = {}
        if part_name is not None:
            name = self._normalize_text(part_name)
            if not name:
                raise ValidationError("“名称”不能为空", field="名称")
            updates["part_name"] = name
        if route_raw is not None:
            updates["route_raw"] = str(route_raw)
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)

        with self.tx_manager.transaction():
            self.part_repo.update(pn, updates)

        return self._get_or_raise(pn)

    def delete(self, part_no: Any) -> None:
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        self._get_or_raise(pn)

        # 若被批次引用则禁止删除（避免排产数据断链）
        row = self.conn.execute("SELECT 1 FROM Batches WHERE part_no = ? LIMIT 1", (pn,)).fetchone()
        if row is not None:
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该零件已被批次引用，不能删除。")

        with self.tx_manager.transaction():
            self.part_repo.delete(pn)

    def delete_all_no_tx(self) -> None:
        self.part_repo.delete_all()

    # -------------------------
    # 解析与模板保存（关键事务边界）
    # -------------------------
    def validate_route_format(self, route_raw: Any) -> Tuple[bool, str]:
        return self.route_parser.validate_format(str(route_raw) if route_raw is not None else "")

    def _parse_route_or_raise(self, *, part_no: str, route_raw: Any, strict_mode: bool = False) -> ParseResult:
        rr = str(route_raw) if route_raw is not None else ""
        ok, msg = self.route_parser.validate_format(rr)
        if not ok:
            raise BusinessError(ErrorCode.ROUTE_PARSE_ERROR, f"工艺路线解析失败：{msg}")

        result = self.route_parser.parse(rr, part_no=part_no, strict_mode=bool(strict_mode))
        if result.status == ParseStatus.FAILED:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "工艺路线解析失败",
                details={"errors": result.errors, "warnings": result.warnings, "stats": result.stats},
            )
        return result

    def parse(self, route_raw: Any, part_no: str, *, strict_mode: bool = False) -> ParseResult:
        return self.route_parser.parse(
            str(route_raw) if route_raw is not None else "", part_no=part_no, strict_mode=bool(strict_mode)
        )

    def reparse_and_save(self, part_no: Any, route_raw: Any, *, strict_mode: bool = False) -> ParseResult:
        """
        重新解析并覆盖保存模板（事务保护）：
        - 更新 Parts.route_raw / route_parsed
        - 清理并重建 PartOperations / ExternalGroups
        """
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        self._get_or_raise(pn)

        rr = str(route_raw) if route_raw is not None else ""
        result = self._parse_route_or_raise(part_no=pn, route_raw=rr, strict_mode=bool(strict_mode))

        with self.tx_manager.transaction():
            # 更新零件字段
            self.part_repo.update(pn, {"route_raw": rr, "route_parsed": "yes"})

            # 清理前快照 internal 工时（用于同 seq 保留）
            old_internal_hours = self._build_internal_hours_snapshot(pn)

            # 清理旧模板
            self.op_repo.delete_by_part(pn)
            self.group_repo.delete_by_part(pn)

            # 保存新模板（默认 separate）
            self._save_template_no_tx(
                part_no=pn,
                parse_result=result,
                preserved_internal_hours=old_internal_hours,
            )

        return result

    def upsert_and_parse_no_tx(self, part_no: str, part_name: str, route_raw: str, *, strict_mode: bool = False) -> ParseResult:
        """
        在“外部已开启事务”的情况下导入零件工艺路线：
        - 不自己开启事务（避免嵌套 commit）
        - 若零件不存在则创建；存在则更新；然后覆盖保存模板
        """
        pn = self._normalize_text(part_no)
        name = self._normalize_text(part_name)
        rr = str(route_raw) if route_raw is not None else ""
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        if not name:
            raise ValidationError("“名称”不能为空", field="名称")
        result = self._parse_route_or_raise(part_no=pn, route_raw=rr, strict_mode=bool(strict_mode))

        # upsert part
        existed = self.part_repo.get(pn)
        if existed:
            self.part_repo.update(pn, {"part_name": name, "route_raw": rr, "route_parsed": YesNo.YES.value})
        else:
            self.part_repo.create({"part_no": pn, "part_name": name, "route_raw": rr, "route_parsed": YesNo.YES.value})

        old_internal_hours = self._build_internal_hours_snapshot(pn)

        # 覆盖模板
        self.op_repo.delete_by_part(pn)
        self.group_repo.delete_by_part(pn)
        self._save_template_no_tx(
            part_no=pn,
            parse_result=result,
            preserved_internal_hours=old_internal_hours,
        )
        return result

    def _save_template_no_tx(
        self,
        part_no: str,
        parse_result: ParseResult,
        preserved_internal_hours: Optional[Dict[int, Tuple[float, float]]] = None,
    ) -> None:
        """
        保存模板（不包含事务控制）。调用方必须保证已在事务中，或可接受多语句写入。
        """
        save_template_no_tx(
            op_repo=self.op_repo,
            group_repo=self.group_repo,
            logger=getattr(self, "logger", None),
            part_no=part_no,
            parse_result=parse_result,
            preserved_internal_hours=preserved_internal_hours,
        )

    # -------------------------
    # 模板读取与编辑（页面使用）
    # -------------------------
    def get_template_detail(self, part_no: str) -> Dict[str, Any]:
        p = self.get(part_no)
        ops = self.op_repo.list_by_part(p.part_no, include_deleted=True)
        groups = self.group_repo.list_by_part(p.part_no)
        group_map = {g.group_id: g for g in groups}
        return {
            "part": p,
            "operations": ops,
            "groups": groups,
            "group_map": group_map,
        }

    def update_internal_hours(self, part_no: str, seq: Any, setup_hours: Any, unit_hours: Any) -> None:
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        self._get_or_raise(pn)

        try:
            s = int(seq)
        except Exception as e:
            raise ValidationError("工序号不合法", field="工序") from e

        sh = self._normalize_float(setup_hours, "换型时间(小时)", allow_none=False)
        uh = self._normalize_float(unit_hours, "单件工时(小时)", allow_none=False)
        if sh is None:
            sh = 0.0
        if uh is None:
            uh = 0.0
        if sh < 0 or uh < 0:
            raise ValidationError("工时不能为负数", field="工时")

        op = self.op_repo.get(pn, s)
        if not op or not op.is_active():
            raise BusinessError(ErrorCode.NOT_FOUND, f"工序 {s} 不存在或已删除")
        if not op.is_internal():
            raise ValidationError("只能编辑自制工序工时", field="工序")

        with self.tx_manager.transaction():
            self.op_repo.update(pn, s, {"setup_hours": float(sh), "unit_hours": float(uh)})

    def delete_external_group(self, part_no: str, group_id: str) -> Dict[str, Any]:
        pn = self._normalize_text(part_no)
        gid = self._normalize_text(group_id)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        if not gid:
            raise ValidationError("缺少外协工序组编号", field="group_id")
        self._get_or_raise(pn)

        return self.delete_guard.delete_external_group(part_no=pn, group_id=gid)

    def calc_deletable_external_group_ids(self, part_no: str) -> List[str]:
        """
        计算当前零件中“可删除”的外部工序组ID（用于页面控制按钮）。
        规则：根据 DeletionValidator.get_deletion_groups() 返回的首/尾外部工序组匹配 group_id。
        """
        pn = self._normalize_text(part_no)
        if not pn:
            return []
        return self.delete_guard.calc_deletable_external_group_ids(pn)

    # -------------------------
    # Excel 辅助
    # -------------------------
    def build_existing_for_excel_routes(self) -> Dict[str, Dict[str, Any]]:
        return build_existing_for_excel_routes(self.part_repo)
