from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import SourceType
from core.services.common.safe_logging import safe_info, safe_warning


class ParseStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"  # 有警告但可用
    FAILED = "failed"


@dataclass
class ParsedOperation:
    """解析后的工序（供保存到 PartOperations 使用）。"""

    seq: int  # 工序号
    op_type_name: str  # 工种名称
    source: str  # internal/external
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
class ExternalGroup:
    """外部工序组（连续 external）。"""

    group_id: str
    start_seq: int
    end_seq: int
    operations: List[ParsedOperation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "start_seq": self.start_seq,
            "end_seq": self.end_seq,
            "operations": [x.to_dict() for x in self.operations],
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

    # 需要移除的分隔符（空格、逗号、顿号、破折号、箭头等）
    # 说明：
    # - 文档/用户输入里常见 "->" / "→" / "-" / "—" 等分隔；若不移除 ">" 会污染工种名（如 "钳>"）。
    # - 这里用“字符集合”覆盖：'-' 与 '>' 分别移除，即可兼容 "->"。
    SEPARATORS = r"[\s,，、\-—–→>＞]+"

    def __init__(self, op_types_repo, suppliers_repo, logger=None):
        self.op_types_repo = op_types_repo
        self.suppliers_repo = suppliers_repo
        self.logger = logger

    def parse(self, route_string: str, part_no: str, *, strict_mode: bool = False) -> ParseResult:
        warnings: List[str] = []
        errors: List[str] = []
        original_input = route_string or ""

        # Step 0: 预处理
        normalized = self._preprocess(route_string)

        if not normalized:
            return ParseResult(
                status=ParseStatus.FAILED,
                operations=[],
                external_groups=[],
                warnings=[],
                errors=["工艺路线为空或格式无效"],
                stats={"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0},
                original_input=original_input,
                normalized_input="",
            )

        # 防御：必须以工序号开头；尾部不能是纯数字（否则会被正则静默丢弃）
        if re.match(r"^\d", normalized) is None:
            errors.append("工艺路线格式无效：必须以工序号开头")
        tail_m = re.search(r"(\d+)$", normalized)
        if tail_m:
            errors.append(f"工艺路线尾部工序号 {tail_m.group(1)} 缺少工种名")

        # 加载配置
        op_types = {ot.name: ot for ot in (self.op_types_repo.list() or [])}
        suppliers, supplier_issues = self._build_supplier_map()

        def _strict_supplier_issue_messages(issue_messages: List[str], *, op_type_name: str) -> List[str]:
            out: List[str] = []
            for raw_msg in issue_messages or []:
                text = str(raw_msg or "").strip()
                if not text:
                    continue
                out.append(text.replace("已按 1.0 天处理", "严格模式已拒绝按 1.0 天处理"))
            if out:
                return out
            return [f"工种“{op_type_name}”供应商默认周期配置无效，严格模式已拒绝按 1.0 天处理"]

        # Step 1: 正则匹配
        pattern = r"(\d+)([^\d]+)"
        matches = re.findall(pattern, normalized)

        if not matches:
            generic = "无法识别工艺路线格式，请使用'工序号+工种名'格式，如'5数铣10钳20数车'"
            final_errors = list(errors or [])
            if generic not in final_errors:
                final_errors.append(generic)
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

        # Step 2: 工种识别
        operations: List[ParsedOperation] = []
        stats = {"total": 0, SourceType.INTERNAL.value: 0, SourceType.EXTERNAL.value: 0, "unknown": 0}
        seen_seqs = set()
        supplier_issue_added = set()

        for seq_str, op_type_name in matches:
            try:
                seq = int(seq_str)
            except Exception:
                warnings.append(f"工序号“{seq_str}”无法解析，将跳过")
                continue

            op_type_name = (op_type_name or "").strip()
            if not op_type_name:
                warnings.append(f"工序号 {seq} 的工种为空，将跳过")
                continue

            # 检查工序号重复
            if seq in seen_seqs:
                warnings.append(f"工序号 {seq} 重复出现，将保留第一个")
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
                # 未识别的工种，默认为外部
                is_internal = False
                is_recognized = False
                if strict_mode:
                    errors.append(f"工种“{op_type_name}”未在系统中配置，严格模式已拒绝默认标记为外部工序")
                    strict_unknown = True
                else:
                    warnings.append(f"工种“{op_type_name}”未在系统中配置，已默认标记为外部工序")
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

            # 外部工序：匹配供应商默认周期（用于初始化 ext_days）
            if not is_internal and not strict_unknown:
                supplier_info = suppliers.get(op_type_name)
                issue_messages = supplier_issues.get(op_type_name) or []
                if supplier_info:
                    op.supplier_id = supplier_info[0]
                    if strict_mode and issue_messages:
                        if op_type_name not in supplier_issue_added:
                            errors.extend(_strict_supplier_issue_messages(issue_messages, op_type_name=op_type_name))
                            supplier_issue_added.add(op_type_name)
                    else:
                        op.default_days = supplier_info[1]
                        if issue_messages and op_type_name not in supplier_issue_added:
                            warnings.extend([msg for msg in issue_messages if msg])
                            supplier_issue_added.add(op_type_name)
                else:
                    if strict_mode:
                        errors.append(
                            f"工种“{op_type_name}”未找到供应商配置，严格模式已拒绝按默认 1.0 天初始化外协周期"
                        )
                    else:
                        op.default_days = 1.0
                        warnings.append(
                            f"工种“{op_type_name}”未找到供应商配置，已按默认 1.0 天初始化外协周期"
                        )

            operations.append(op)

        # 按工序号排序
        operations.sort(key=lambda x: x.seq)

        # Step 3: 识别连续外部工序组
        external_groups = self._identify_external_groups(operations, part_no)

        # Step 4: 状态
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
        """预处理工艺路线字符串（移除分隔符、全角转半角）。"""
        if not route_string:
            return ""

        # 1) 去除首尾空格
        result = str(route_string).strip()
        if not result:
            return ""

        # 2) 移除常见分隔符
        result = re.sub(self.SEPARATORS, "", result)

        # 3) 全角数字转半角
        full_to_half = str.maketrans("０１２３４５６７８９", "0123456789")
        result = result.translate(full_to_half)

        return result

    def _resolve_supplier_op_type_name(self, supplier: Any, supplier_id: str) -> Optional[str]:
        try:
            op_type = self.op_types_repo.get(supplier.op_type_id)
        except Exception as exc:
            safe_warning(self.logger, f"供应商“{supplier_id}”工种映射加载失败（op_type_id={supplier.op_type_id!r}）：{exc}")
            return None
        name = getattr(op_type, "name", None) if op_type else None
        return str(name) if name else None

    @staticmethod
    def _resolve_supplier_default_days(
        supplier: Any,
        *,
        supplier_id: str,
        op_type_name: str,
        has_default_days: bool,
    ) -> Tuple[float, List[str]]:
        raw_default_days: Any = getattr(supplier, "default_days", None)
        if not has_default_days:
            return 1.0, [f"供应商“{supplier_id}”未配置默认周期，工种“{op_type_name}”已按 1.0 天处理"]
        if raw_default_days is None or (isinstance(raw_default_days, str) and raw_default_days.strip() == ""):
            return 1.0, [f"供应商“{supplier_id}”默认周期为空，工种“{op_type_name}”已按 1.0 天处理"]
        try:
            parsed_default_days = float(raw_default_days)
        except Exception:
            return 1.0, [f"供应商“{supplier_id}”默认周期无法解析，工种“{op_type_name}”已按 1.0 天处理"]
        if not math.isfinite(parsed_default_days) or parsed_default_days <= 0:
            return 1.0, [f"供应商“{supplier_id}”默认周期无效，工种“{op_type_name}”已按 1.0 天处理"]
        return float(parsed_default_days), []

    @staticmethod
    def _effective_supplier_order_key(supplier_id: str) -> Tuple[str]:
        return (str(supplier_id or "").strip(),)

    @classmethod
    def _candidate_supplier_should_replace_current(
        cls,
        current_supplier_id: Optional[str],
        candidate_supplier_id: str,
    ) -> bool:
        """
        当前冻结规则：
        - 同一工种出现多个候选供应商时，按 supplier_id 字典序取最大者作为“有效供应商”；
        - 该规则是为了让路线解析、预览基线与确认导入保持同口径；
        - 它表达的是当前兼容排序规则，不等价于更广义的业务优先级。
        """
        if current_supplier_id is None:
            return True
        return cls._effective_supplier_order_key(candidate_supplier_id) > cls._effective_supplier_order_key(current_supplier_id)

    def _build_supplier_map(self) -> Tuple[Dict[str, Tuple[str, float]], Dict[str, List[str]]]:
        """
        构建 工种名 -> (supplier_id, default_days) 映射。
        规则：仅使用 Suppliers.op_type_id 有值且能映射到 OpTypes 的记录；
        若同一工种存在多条供应商记录，则按 supplier_id 字典序取最后一条
        （即 supplier_id 最大者）作为有效供应商，与预览基线保持一致。
        """
        supplier_map: Dict[str, Tuple[str, float]] = {}
        issues: Dict[str, List[str]] = {}
        for supplier in (self.suppliers_repo.list() or []):
            if not getattr(supplier, "op_type_id", None):
                continue
            supplier_id = str(getattr(supplier, "supplier_id", "") or "").strip() or "?"
            op_type_name = self._resolve_supplier_op_type_name(supplier, supplier_id)
            if not op_type_name:
                continue
            default_days, issue_messages = self._resolve_supplier_default_days(
                supplier,
                supplier_id=supplier_id,
                op_type_name=op_type_name,
                has_default_days=hasattr(supplier, "default_days"),
            )
            current = supplier_map.get(op_type_name)
            current_supplier_id = None if current is None else str(current[0] or "").strip()
            if not self._candidate_supplier_should_replace_current(current_supplier_id, supplier_id):
                continue
            supplier_map[op_type_name] = (supplier_id, float(default_days))
            if issue_messages:
                issues[op_type_name] = list(issue_messages)
            else:
                # 同一工种按 supplier_id 取“有效供应商”时，必须同步清掉旧候选供应商遗留的错误信息；
                # 否则 strict_mode 可能因为已被淘汰的低优先级供应商而误报/误拒绝。
                issues.pop(op_type_name, None)

        return supplier_map, issues

    def _identify_external_groups(self, operations: List[ParsedOperation], part_no: str) -> List[ExternalGroup]:
        """识别连续外部工序组，并给外部工序填充 ext_group_id。"""
        groups: List[ExternalGroup] = []
        current_group: Optional[ExternalGroup] = None
        group_counter = 1

        for op in operations:
            if op.source == SourceType.EXTERNAL.value:
                if current_group is None:
                    group_id = f"{part_no}_EXT_{group_counter}"
                    current_group = ExternalGroup(
                        group_id=group_id,
                        start_seq=op.seq,
                        end_seq=op.seq,
                        operations=[op],
                    )
                    op.ext_group_id = group_id
                else:
                    current_group.end_seq = op.seq
                    current_group.operations.append(op)
                    op.ext_group_id = current_group.group_id
            else:
                if current_group is not None:
                    groups.append(current_group)
                    current_group = None
                    group_counter += 1

        if current_group is not None:
            groups.append(current_group)

        return groups

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
