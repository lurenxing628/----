"""回归测试：RouteParser.parse 解析工艺路线时，OpType.category 为大写带空格(如「 INTERNAL 」)仍应归类为 internal 工序，stats 统计 internal=1/external=0。"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import List


@dataclass
class _StubOpTypesRepo:
    op_types: List[object]

    def list(self):
        return list(self.op_types)

    def get(self, op_type_id: str):
        for ot in self.op_types:
            if getattr(ot, "op_type_id", None) == op_type_id:
                return ot
        return None


@dataclass
class _StubSuppliersRepo:
    def list(self):
        return []


def test_route_parser_op_type_category_case_insensitive() -> None:

    from core.services.process.route_parser import ParseStatus, RouteParser

    # 关键：category 为大写/带空格时，仍应被识别为 internal
    ot = SimpleNamespace(op_type_id="OT001", name="数铣", category=" INTERNAL ")
    op_repo = _StubOpTypesRepo(op_types=[ot])
    sup_repo = _StubSuppliersRepo()

    parser = RouteParser(op_types_repo=op_repo, suppliers_repo=sup_repo, logger=None)
    result = parser.parse("5数铣", part_no="P001")

    assert result.status == ParseStatus.SUCCESS.value or result.status == ParseStatus.SUCCESS, f"解析状态异常：{result.status!r}"
    assert result.operations and result.operations[0].source == "internal", f"category 大小写容错失败：{result.operations!r}"
    assert result.stats.get("internal") == 1 and result.stats.get("external") == 0, f"统计异常：{result.stats!r}"


