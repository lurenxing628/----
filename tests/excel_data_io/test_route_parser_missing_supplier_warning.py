"""回归测试：RouteParser.parse 解析外部工序（如「5表处理」）但供应商库为空时，返回 PARTIAL 状态、工序 source=external、default_days 临时按 1 天处理，并透出含「没有找到可用的外协供应商」的 warning 而非静默吞掉。"""

from dataclasses import dataclass
from typing import List


@dataclass
class _OpType:
    op_type_id: str
    name: str
    category: str


@dataclass
class _StubOpTypesRepo:
    op_types: List[_OpType]

    def list(self):
        return list(self.op_types)

    def get(self, op_type_id: str):
        for item in self.op_types:
            if item.op_type_id == op_type_id:
                return item
        return None


@dataclass
class _StubSuppliersRepo:
    suppliers: List[object]

    def list(self):
        return list(self.suppliers)


def test_route_parser_missing_supplier_warning() -> None:

    from core.services.process.route_parser import ParseStatus, RouteParser

    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(suppliers=[]),
        logger=None,
    )
    result = parser.parse("5表处理", part_no="P_NO_SUP")

    assert result.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), f"缺可用外协供应商应返回 PARTIAL：{result.status!r}"
    assert len(result.operations or []) == 1, f"外部工序解析数量异常：{result.operations!r}"

    op = result.operations[0]
    assert str(op.source or "").strip().lower() == "external", f"工序来源异常：{op.source!r}"
    assert abs(float(op.default_days or 0.0) - 1.0) < 1e-9, f"默认周期未临时按 1 天处理：{op.default_days!r}"
    assert any("没有找到可用的外协供应商" in str(msg) for msg in (result.warnings or [])), (
        f"未透出缺供应商 warning：{result.warnings!r}"
    )
