from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


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

    def parse(self, route_string: str, part_no: str) -> ParseResult:
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
                stats={"total": 0, "internal": 0, "external": 0, "unknown": 0},
                original_input=original_input,
                normalized_input="",
            )

        # 加载配置
        op_types = {ot.name: ot for ot in (self.op_types_repo.list() or [])}
        suppliers = self._build_supplier_map()

        # Step 1: 正则匹配
        pattern = r"(\d+)([^\d]+)"
        matches = re.findall(pattern, normalized)

        if not matches:
            return ParseResult(
                status=ParseStatus.FAILED,
                operations=[],
                external_groups=[],
                warnings=[],
                errors=["无法识别工艺路线格式，请使用'工序号+工种名'格式，如'5数铣10钳20数车'"],
                stats={"total": 0, "internal": 0, "external": 0, "unknown": 0},
                original_input=original_input,
                normalized_input=normalized,
            )

        # Step 2: 工种识别
        operations: List[ParsedOperation] = []
        stats = {"total": 0, "internal": 0, "external": 0, "unknown": 0}
        seen_seqs = set()

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
            if op_type:
                cat = str(getattr(op_type, "category", None) or "internal").strip().lower() or "internal"
                is_internal = cat == "internal"
                is_recognized = True
            else:
                # 未识别的工种，默认为外部
                is_internal = False
                is_recognized = False
                warnings.append(f"工种“{op_type_name}”未在系统中配置，已默认标记为外部工序")
                stats["unknown"] += 1

            source = "internal" if is_internal else "external"
            if is_internal:
                stats["internal"] += 1
            else:
                stats["external"] += 1

            op = ParsedOperation(
                seq=seq,
                op_type_name=op_type_name,
                op_type_id=(op_type.op_type_id if op_type else None),
                source=source,
                is_recognized=is_recognized,
            )

            # 外部工序：匹配供应商默认周期（用于初始化 ext_days）
            if not is_internal:
                supplier_info = suppliers.get(op_type_name)
                if supplier_info:
                    op.supplier_id = supplier_info[0]
                    op.default_days = supplier_info[1]
                else:
                    op.default_days = 1.0  # 默认 1 天

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
            try:
                self.logger.info(
                    f"工艺路线解析：{part_no} 共{stats['total']}道（内部{stats['internal']} 外部{stats['external']} 未识别{stats['unknown']}）"
                )
            except Exception:
                pass

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

    def _build_supplier_map(self) -> Dict[str, Tuple[str, float]]:
        """
        构建 工种名 -> (supplier_id, default_days) 映射。
        规则：仅使用 Suppliers.op_type_id 有值且能映射到 OpTypes 的记录。
        """
        result: Dict[str, Tuple[str, float]] = {}
        for supplier in (self.suppliers_repo.list() or []):
            if not getattr(supplier, "op_type_id", None):
                continue
            try:
                op_type = self.op_types_repo.get(supplier.op_type_id)
            except Exception:
                op_type = None
            if not op_type:
                continue
            name = getattr(op_type, "name", None)
            if not name:
                continue
            result[str(name)] = (supplier.supplier_id, float(getattr(supplier, "default_days", 1.0) or 1.0))
        return result

    def _identify_external_groups(self, operations: List[ParsedOperation], part_no: str) -> List[ExternalGroup]:
        """识别连续外部工序组，并给外部工序填充 ext_group_id。"""
        groups: List[ExternalGroup] = []
        current_group: Optional[ExternalGroup] = None
        group_counter = 1

        for op in operations:
            if op.source == "external":
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
        pattern = r"(\d+)([^\d]+)"
        matches = re.findall(pattern, normalized)

        if not matches:
            return False, "格式无效，请使用“工序号+工种名”格式"

        if len(matches) < 1:
            return False, "至少需要一道工序"

        return True, f"格式有效，识别到 {len(matches)} 道工序"

