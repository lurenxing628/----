from __future__ import annotations

import re
from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.transaction import TransactionManager
from core.models.enums import SourceType
from core.models.resource_capabilities import supports_source
from core.services.common.safe_logging import safe_info
from core.services.process.route_parser_constraints import SupplierConstraintResolver, SupplierGlobalIssue
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
    compact_name_ambiguities,
    parse_explicit_route,
    preprocess_route_string,
    route_format_errors,
    route_tokens,
    serialize_route_rows,
)
from data.repositories.op_type_repo import OpTypeRepository


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


@dataclass
class RouteParseContext:
    """一次解析所需的纯数据快照：工种名映射 + 供应商映射/问题/全局问题。

    供批量解析（Excel 路线预览/导入、批次基线快照）在循环外构建一次、经 parse(context=...) 复用，
    避免每条路线都重查 OpTypes/Suppliers（消除 N+1）。缓存的是纯数据而非 resolver 实例；
    要求复用窗口内 OpTypes/Suppliers 不被改动（预览/导入循环只写 Parts/PartOperations，不改这两张表）。
    """

    op_types: Dict[str, Any]
    suppliers: Dict[str, Tuple[str, float]]
    supplier_issues: Dict[str, List[str]]
    supplier_global_issues: List[SupplierGlobalIssue]


def _explicit_format_errors(rows):
    errors, seen = [], set()
    for seq, name in rows:
        if len(seq) > 19 or not 0 < int(seq) <= (1 << 63) - 1:
            errors.append("工序号必须是正整数，而且不能超出可用范围。")
        elif int(seq) in seen:
            errors.append("工序号 " + seq + " 重复，请核对。")
        seen.add(int(seq) if len(seq) <= 19 else seq)
        if not name.strip():
            errors.append("工序 " + seq + " 缺少工种名称。")
    return errors


def _route_matches(explicit, normalized, op_types, errors):
    matches = explicit if explicit is not None else route_tokens(normalized)
    if explicit is None:
        errors.extend(message for _, message in compact_name_ambiguities(matches, op_types))
    if explicit is not None and errors:
        return []
    return matches


def _empty_parse_result(original_input, normalized, warnings, errors):
    return ParseResult(status=ParseStatus.FAILED, operations=[], external_groups=[], warnings=warnings, errors=errors,
                       stats={"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0},
                       original_input=original_input, normalized_input=normalized)


def _validate_compact_format(normalized):
    if not normalized:
        return False, "工艺路线不能为空"
    if re.match(r"^\d", normalized) is None:
        return False, "格式无效：必须以工序号开头"
    tail_m = re.search(r"(\d+)$", normalized)
    if tail_m:
        return False, f"格式无效：尾部工序号 {tail_m.group(1)} 缺少工种名"
    matches = re.findall(r"(\d+)([^\d]+)", normalized)
    if not matches:
        return False, "格式无效，请使用“工序号+工种名”格式"
    return True, f"格式有效，识别到 {len(matches)} 道工序"


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

    def build_parse_context(self) -> RouteParseContext:
        """一次性构建解析纯数据（工种名映射 + 供应商映射/问题/全局问题），供批量解析循环外复用。"""
        concrete = type(self.op_types_repo) is OpTypeRepository
        scope = TransactionManager(self.op_types_repo.conn).transaction() if concrete else nullcontext()
        with scope:
            records = self.op_types_repo.list() or []
            op_types = {ot.name: ot for ot in records}
            # Injected readers retain their own get semantics, including mapping
            # failures. Concrete SQL rows are captured in one actual read snapshot.
            by_id = {ot.op_type_id: ot for ot in records} if concrete else None
            suppliers, supplier_issues, supplier_global_issues = self._build_supplier_map_with_global_issues(by_id)
        return RouteParseContext(
            op_types=op_types,
            suppliers=suppliers,
            supplier_issues=supplier_issues,
            supplier_global_issues=supplier_global_issues,
        )

    def parse(
        self,
        route_string: str,
        part_no: str,
        *,
        strict_mode: bool = False,
        context: Optional[RouteParseContext] = None,
    ) -> ParseResult:
        errors: List[str] = []
        normalized, explicit = self._read_route_input(route_string, errors)
        return self._parse_input(route_string, part_no, normalized, explicit, errors,
                                 strict_mode=strict_mode, context=context)

    def parse_with_format_check(self, route_string, part_no, *, strict_mode=False, context=None) -> Tuple[bool, str, Optional[ParseResult]]:
        """Template saves consume the same decoded input as the early format check."""
        errors = []
        normalized, explicit = self._read_route_input(route_string, errors)
        ok, message = self._input_format(route_string, normalized, explicit, errors)
        if not ok:
            return False, message, None
        result = self._parse_input(route_string, part_no, normalized, explicit, errors,
                                   strict_mode=strict_mode, context=context, format_checked=True)
        return True, message, result

    def _parse_input(self, route_string, part_no, normalized, explicit, errors, *, strict_mode, context, format_checked=False) -> ParseResult:
        warnings: List[str] = []
        original_input = route_string or ""
        if not normalized and not errors:
            return _empty_parse_result(original_input, "", [], [EMPTY_ROUTE_ERROR])
        if not format_checked:
            errors.extend(route_format_errors(normalized) if explicit is None else _explicit_format_errors(explicit))
        # 单次解析 context=None → 每次重建（行为与历史逐字一致）；批量解析传入循环外构建的 context 复用，消除 N+1。
        ctx = context if context is not None else self.build_parse_context()
        op_types = ctx.op_types
        suppliers = ctx.suppliers
        supplier_issues = ctx.supplier_issues
        supplier_global_issues = ctx.supplier_global_issues
        matches = _route_matches(explicit, normalized, op_types, errors)
        if not matches:
            self._apply_supplier_global_issues(
                supplier_global_issues=supplier_global_issues,
                operations=[],
                warnings=warnings,
                errors=errors,
                strict_mode=strict_mode,
            )
            final_errors = list(errors or [])
            if GENERIC_FORMAT_ERROR not in final_errors:
                final_errors.append(GENERIC_FORMAT_ERROR)
            return _empty_parse_result(original_input, normalized, warnings, final_errors)

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
        self._apply_supplier_global_issues(
            supplier_global_issues=supplier_global_issues,
            operations=operations,
            warnings=warnings,
            errors=errors,
            strict_mode=strict_mode,
        )
        return self._completed_parse(part_no, original_input, normalized, operations, stats, warnings, errors)

    def _read_route_input(self, route_string, errors):
        try:
            explicit = parse_explicit_route(route_string or "")
        except ValueError as exc:
            explicit = []
            errors.append(str(exc))
        normalized = serialize_route_rows(explicit) if explicit is not None else self._preprocess(route_string)
        return normalized, explicit

    def _completed_parse(self, part_no, original_input, normalized, operations, stats, warnings, errors):
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
        supplier_map, supplier_issues, _global_issues = self._build_supplier_map_with_global_issues()
        return supplier_map, supplier_issues

    def _build_supplier_map_with_global_issues(
        self,
        op_types_by_id=None,
    ) -> Tuple[Dict[str, Tuple[str, float]], Dict[str, List[str]], List[SupplierGlobalIssue]]:
        resolver = SupplierConstraintResolver(
            self.op_types_repo,
            self.suppliers_repo,
            logger=self.logger,
            op_types_by_id=op_types_by_id,
        )
        supplier_map, supplier_issues = resolver.build_supplier_map()
        return supplier_map, supplier_issues, list(resolver.global_issues)

    def _apply_supplier_global_issues(
        self,
        *,
        supplier_global_issues: List[SupplierGlobalIssue],
        operations: List[ParsedOperation],
        warnings: List[str],
        errors: List[str],
        strict_mode: bool,
    ) -> None:
        referenced_external_op_type_ids = {
            str(op.op_type_id or "").strip()
            for op in operations
            if op.source == SourceType.EXTERNAL.value and str(op.op_type_id or "").strip()
        }
        for issue in supplier_global_issues:
            message = str(issue.message or "").strip()
            if not message:
                continue
            op_type_id = str(issue.op_type_id or "").strip()
            if strict_mode and op_type_id in referenced_external_op_type_ids:
                errors.append(message)
            else:
                warnings.append(message)

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
                is_internal = supports_source(cat, SourceType.INTERNAL.value)
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
        errors = []
        normalized, explicit = self._read_route_input(route_string, errors)
        return self._input_format(route_string, normalized, explicit, errors)

    @staticmethod
    def _input_format(route_string, normalized, explicit, errors):
        if not route_string or not str(route_string).strip():
            return False, "工艺路线不能为空"
        if errors:
            return False, errors[0]
        if explicit is not None:
            if _explicit_format_errors(explicit):
                return False, "工序号必须为不重复的正整数，每道工序都要有名称。"
            return True, f"格式有效，识别到 {len(explicit)} 道工序"
        return _validate_compact_format(normalized)
