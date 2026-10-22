from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple, cast

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Part
from core.models.enums import YesNo
from core.services.common.normalize import normalize_text
from data.repositories import (
    ExternalGroupRepository,
    OpTypeRepository,
    PartOperationRepository,
    PartRepository,
    SupplierRepository,
)

from .part_route_validation import (
    build_internal_hours_snapshot,
    save_template_no_tx,
)
from .route_parser import ParseResult, ParseStatus, RouteParser
from .template_hours import ProcessTemplateHours


class PartService:
    """零件与工艺模板服务（Parts/PartOperations/ExternalGroups）。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.tx_manager = TransactionManager(conn)

        self.part_repo = PartRepository(conn, logger=logger)
        self.op_repo = PartOperationRepository(conn, logger=logger)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)
        self.op_type_repo = OpTypeRepository(conn, logger=logger)
        self.supplier_repo = SupplierRepository(conn, logger=logger)

        self.route_parser = RouteParser(self.op_type_repo, self.supplier_repo, logger=logger)

    # -------------------------
    # 工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_float(value: Any, field: str) -> float:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return 0.0
        if isinstance(value, bool):
            raise ValidationError(f"“{field}”必须是数字", field=field)
        try:
            parsed = float(value)
        except Exception as e:
            raise ValidationError(f"“{field}”必须是数字", field=field) from e
        if not math.isfinite(parsed):
            raise ValidationError(f"“{field}”必须是有限数字", field=field)
        return parsed

    def _get_or_raise(self, part_no: str) -> Part:
        p = self.part_repo.get(part_no)
        if not p:
            raise BusinessError(ErrorCode.PART_NOT_FOUND, f"零件“{part_no}”不存在")
        return p

    def _build_internal_hours_snapshot(self, part_no: str) -> Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]]:
        return build_internal_hours_snapshot(self.op_repo, part_no)

    # -------------------------
    # 解析与模板保存（关键事务边界）
    # -------------------------

    def _parse_route_or_raise(
        self, *, part_no: str, route_raw: str, strict_mode: bool = False
    ) -> ParseResult:
        ok, msg, result = self.route_parser.parse_with_format_check(
            route_raw, part_no=part_no, strict_mode=strict_mode)
        if not ok:
            raise BusinessError(ErrorCode.ROUTE_PARSE_ERROR, f"工艺路线解析失败：{msg}")

        # The successful format branch always returns the completed parse.
        result = cast(ParseResult, result)
        if result.status == ParseStatus.FAILED:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "工艺路线解析失败",
                details={"errors": result.errors, "warnings": result.warnings, "stats": result.stats},
            )
        return result

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
        result = self._parse_route_or_raise(part_no=pn, route_raw=rr, strict_mode=strict_mode)

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

    def upsert_and_parse_no_tx(
        self,
        part_no: str,
        part_name: str,
        route_raw: str,
        *,
        strict_mode: bool = False,
    ) -> ParseResult:
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
        result = self._parse_route_or_raise(part_no=pn, route_raw=rr, strict_mode=strict_mode)

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
        preserved_internal_hours: Optional[Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]]] = None,
    ) -> None:
        """
        保存模板（不包含事务控制）。调用方必须保证已在事务中，或可接受多语句写入。
        """
        save_template_no_tx(
            op_repo=self.op_repo,
            group_repo=self.group_repo,
            part_no=part_no,
            parse_result=parse_result,
            preserved_internal_hours=preserved_internal_hours,
        )

    # -------------------------
    # 模板读取与编辑（页面使用）
    # -------------------------

    def _normalize_internal_hours(self, setup_hours: object, unit_hours: object) -> Tuple[float, float]:
        sh = self._normalize_float(setup_hours, "换型时间(小时)")
        uh = self._normalize_float(unit_hours, "单件工时(小时)")
        if sh < 0 or uh < 0:
            raise ValidationError("工时不能为负数", field="工时")
        return sh, uh

    def update_internal_hours(self, part_no: str, seq: Any, setup_hours: Any, unit_hours: Any) -> None:
        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        self._get_or_raise(pn)

        try:
            s = int(seq)
        except Exception as e:
            raise ValidationError("工序号不合法", field="工序") from e

        sh, uh = self._normalize_internal_hours(setup_hours, unit_hours)

        op = self.op_repo.get(pn, s)
        if not op or not op.is_active():
            raise BusinessError(ErrorCode.NOT_FOUND, f"工序 {s} 不存在或已删除")
        if not op.is_internal():
            raise ValidationError("只能编辑内部工序工时", field="工序")

        hours = ProcessTemplateHours(self.conn)
        ref = hours.bind(pn, s)
        with self.tx_manager.transaction(begin_immediate=True):
            current = hours.current([ref])[ref]
            if current["source"] != "internal":
                raise ValidationError("只能编辑内部工序工时", field="工序")
            if current["part_no"] != pn or current["seq"] != s or current["id"] != op.id:
                raise BusinessError(ErrorCode.NOT_FOUND, "这道模板工序已经变了，同工序号现在是另一条记录，这次没有更新工时。请刷新后重新核对再保存。")
            hours.revise_current(current, {"setup_hours": sh, "unit_hours": uh}, expected_revision=current["revision"])
