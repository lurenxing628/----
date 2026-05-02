from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import SourceType
from core.services.common.safe_logging import safe_info
from core.services.process.route_parser_constraints import SupplierConstraintResolver
from core.services.process.route_parser_errors import (
    EMPTY_ROUTE_ERROR,
    GENERIC_FORMAT_ERROR,
    duplicate_seq_warning,
    empty_op_warning,
    invalid_seq_warning,
    relaxed_missing_supplier_warning,
    relaxed_unknown_op_warning,
    strict_missing_supplier_error,
    strict_supplier_issue_messages,
    strict_unknown_op_error,
)
from core.services.process.route_parser_segments import ExternalGroup, identify_external_groups
from core.services.process.route_parser_tokens import (
    SEPARATORS as ROUTE_SEPARATORS,
)
from core.services.process.route_parser_tokens import (
    preprocess_route_string,
    route_format_errors,
    route_tokens,
)


class ParseStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"  # 有警告但可用
    FAILED = "failed"


@dataclass
class ParsedOperation:
    """解析后的工序（供保存到 PartOperations 使用）。"""

    seq: int  # 工序号
    op_type_name: str  # 工种名称
    source: str  # 内部/外协
    op_type_id: Optional[str] = None
    supplier_id: Optional[str] = None
    default_days: Optional[float] = None  # 外部工序默认周期（用于初始化 ext_days）
    ext_group_id: Optional[str] = None
    is_recognized: bool = True  # 是否识别的工种

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "op_type_name": self.op_type_name,
            "source": self.source,
            "op_type_id": self.op_type_id,
            "supplier_id": self.supplier_id,
            "default_days": self.default_days,
            "ext_group_id": self.ext_group_id,
            "is_recognized": self.is_recognized,
        }


@dataclass
class ParseResult:
    """解析结果（用于 UI 展示与保存模板）。"""

    status: ParseStatus
    operations: List[ParsedOperation]
    external_groups: List[ExternalGroup]
    warnings: List[str]
    errors: List[str]
    stats: Dict[str, int]
    original_input: str
    normalized_input: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "operations": [x.to_dict() for x in self.operations],
            "external_groups": [g.to_dict() for g in self.external_groups],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "stats": dict(self.stats),
            "original_input": self.original_input,
            "normalized_input": self.normalized_input,
        }


class RouteParser:
    """
    工艺路线解析器（按开发文档 7.x“预处理 + 容错 + 报告”保留核心逻辑）。

    依赖：
    - op_types_repo: 需要支持 list()/get()/get_by_name()
    - suppliers_repo: 需要支持 list()
    """

    SEPARATORS = ROUTE_SEPARATORS

    def __init__(self, op_types_repo, suppliers_repo, logger=None):
        self.op_types_repo = op_types_repo
        self.suppliers_repo = suppliers_repo
        self.logger = logger

    def parse(self, route_string: str, part_no: str, *, strict_mode: bool = False) -> ParseResult:
        warnings: List[str] = []
        errors: List[str] = []
        original_input = route_string or ""
        normalized = self._preprocess(route_string)

        if not normalized:
            return ParseResult(
                status=ParseStatus.FAILED,
                operations=[],
                external_groups=[],
                warnings=[],
                errors=[EMPTY_ROUTE_ERROR],
                stats={"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0},
                original_input=original_input,
                normalized_input="",
            )

        errors.extend(route_format_errors(normalized))
        op_types = {ot.name: ot for ot in (self.op_types_repo.list() or [])}
        suppliers, supplier_issues = self._build_supplier_map()
        matches = route_tokens(normalized)

        if not matches:
            final_errors = list(errors or [])
            if GENERIC_FORMAT_ERROR not in final_errors:
                final_errors.append(GENERIC_FORMAT_ERROR)
            return ParseResult(
                status=ParseStatus.FAILED,
                operations=[],
                external_groups=[],
                warnings=[],
                errors=final_errors,
                stats={"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0},
                original_input=original_input,
                normalized_input=normalized,
            )

        operations, stats = self._parse_operations(
            matches=matches,
            op_types=op_types,
            suppliers=suppliers,
            supplier_issues=supplier_issues,
            warnings=warnings,
            errors=errors,
            strict_mode=strict_mode,
        )
        operations.sort(key=lambda x: x.seq)
        external_groups = self._identify_external_groups(operations, part_no)

        if errors:
            status = ParseStatus.FAILED
        elif warnings:
            status = ParseStatus.PARTIAL
        else:
            status = ParseStatus.SUCCESS

        result = ParseResult(
            status=status,
            operations=operations,
            external_groups=external_groups,
            warnings=warnings,
            errors=errors,
            stats=stats,
            original_input=original_input,
            normalized_input=normalized,
        )

        if self.logger:
            safe_info(
                self.logger,
                f"工艺路线解析：{part_no} 共{stats['total']}道（内部{stats[SourceType.INTERNAL.value]} 外部{stats[SourceType.EXTERNAL.value]} 未识别{stats['unknown']}）",
            )

        return result

    def _preprocess(self, route_string: str) -> str:
        return preprocess_route_string(route_string)

    def _build_supplier_map(self) -> Tuple[Dict[str, Tuple[str, float]], Dict[str, List[str]]]:
        return SupplierConstraintResolver(
            self.op_types_repo,
            self.suppliers_repo,
            logger=self.logger,
        ).build_supplier_map()

    def _parse_operations(
        self,
        *,
        matches: List[Tuple[str, str]],
        op_types: Dict[str, Any],
        suppliers: Dict[str, Tuple[str, float]],
        supplier_issues: Dict[str, List[str]],
        warnings: List[str],
        errors: List[str],
        strict_mode: bool,
    ) -> Tuple[List[ParsedOperation], Dict[str, int]]:
        operations: List[ParsedOperation] = []
        stats = {"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0}
        seen_seqs = set()
        supplier_issue_added = set()

        for seq_str, op_type_name in matches:
            try:
                seq = int(seq_str)
            except Exception:
                warnings.append(invalid_seq_warning(seq_str))
                continue

            op_type_name = (op_type_name or "").strip()
            if not op_type_name:
                warnings.append(empty_op_warning(seq))
                continue

            if seq in seen_seqs:
                warnings.append(duplicate_seq_warning(seq))
                continue
            seen_seqs.add(seq)

            stats["total"] += 1
            op_type = op_types.get(op_type_name)
            strict_unknown = False
            if op_type:
                cat = (
                    str(getattr(op_type, "category", None) or SourceType.INTERNAL.value).strip().lower()
                    or SourceType.INTERNAL.value
                )
                is_internal = cat == SourceType.INTERNAL.value
                is_recognized = True
            else:
                is_internal = False
                is_recognized = False
                if strict_mode:
                    errors.append(strict_unknown_op_error(op_type_name))
                    strict_unknown = True
                else:
                    warnings.append(relaxed_unknown_op_warning(op_type_name))
                stats["unknown"] += 1

            source = SourceType.INTERNAL.value if is_internal else SourceType.EXTERNAL.value
            if is_internal:
                stats[SourceType.INTERNAL.value] += 1
            else:
                stats[SourceType.EXTERNAL.value] += 1

            op = ParsedOperation(
                seq=seq,
                op_type_name=op_type_name,
                op_type_id=(op_type.op_type_id if op_type else None),
                source=source,
                is_recognized=is_recognized,
            )
            if not is_internal and not strict_unknown:
                self._apply_supplier_constraints(
                    op,
                    suppliers=suppliers,
                    supplier_issues=supplier_issues,
                    supplier_issue_added=supplier_issue_added,
                    warnings=warnings,
                    errors=errors,
                    strict_mode=strict_mode,
                )
            operations.append(op)

        return operations, stats

    def _apply_supplier_constraints(
        self,
        op: ParsedOperation,
        *,
        suppliers: Dict[str, Tuple[str, float]],
        supplier_issues: Dict[str, List[str]],
        supplier_issue_added: set,
        warnings: List[str],
        errors: List[str],
        strict_mode: bool,
    ) -> None:
        supplier_info = suppliers.get(op.op_type_name)
        issue_messages = supplier_issues.get(op.op_type_name) or []
        if supplier_info:
            op.supplier_id = supplier_info[0]
            if strict_mode and issue_messages:
                if op.op_type_name not in supplier_issue_added:
                    errors.extend(strict_supplier_issue_messages(issue_messages, op_type_name=op.op_type_name))
                    supplier_issue_added.add(op.op_type_name)
            else:
                op.default_days = supplier_info[1]
                if issue_messages and op.op_type_name not in supplier_issue_added:
                    warnings.extend([msg for msg in issue_messages if msg])
                    supplier_issue_added.add(op.op_type_name)
            return

        if strict_mode:
            errors.append(strict_missing_supplier_error(op.op_type_name))
            return

        op.default_days = 1.0
        warnings.append(relaxed_missing_supplier_warning(op.op_type_name))

    def _identify_external_groups(self, operations: List[ParsedOperation], part_no: str) -> List[ExternalGroup]:
        return identify_external_groups(operations, part_no)

    def validate_format(self, route_string: str) -> Tuple[bool, str]:
        """
        快速验证格式是否可解析（不做完整解析）。

        Returns:
            (是否有效, 提示信息)
        """
        if not route_string or not str(route_string).strip():
            return False, "工艺路线不能为空"

        normalized = self._preprocess(route_string)
        if not normalized:
            return False, "工艺路线不能为空"

        if re.match(r"^\d", normalized) is None:
            return False, "格式无效：必须以工序号开头"
        tail_m = re.search(r"(\d+)$", normalized)
        if tail_m:
            return False, f"格式无效：尾部工序号 {tail_m.group(1)} 缺少工种名"

        pattern = r"(\d+)([^\d]+)"
        matches = re.findall(pattern, normalized)

        if not matches:
            return False, "格式无效，请使用“工序号+工种名”格式"

        return True, f"格式有效，识别到 {len(matches)} 道工序"
