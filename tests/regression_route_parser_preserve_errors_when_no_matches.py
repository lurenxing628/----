"""回归测试：RouteParser.parse 解析无法识别的工艺路线串（如 ABC5）时返回 FAILED，并保留全部细粒度错误——“必须以工序号开头”“尾部工序号 5 缺少工种名”以及“无法识别工艺路线格式”通用错误都不被吞掉。"""

from dataclasses import dataclass
from typing import List


@dataclass
class _StubOpTypesRepo:
    op_types: List[object]

    def list(self):
        return list(self.op_types)

    def get(self, op_type_id: str):
        return None


@dataclass
class _StubSuppliersRepo:
    def list(self):
        return []


def test_route_parser_preserve_errors_when_no_matches() -> None:

    from core.services.process.route_parser import ParseStatus, RouteParser

    parser = RouteParser(op_types_repo=_StubOpTypesRepo(op_types=[]), suppliers_repo=_StubSuppliersRepo(), logger=None)
    result = parser.parse("ABC5", part_no="P_ERRS")

    assert result.status == ParseStatus.FAILED.value or result.status == ParseStatus.FAILED, f"解析状态异常：{result.status!r}"
    errs = list(result.errors or [])

    assert any("必须以工序号开头" in e for e in errs), f"缺少“必须以工序号开头”错误：{errs!r}"
    assert any("尾部工序号 5 缺少工种名" in e for e in errs), f"缺少“尾部工序号 5 缺少工种名”错误：{errs!r}"
    assert any("无法识别工艺路线格式" in e for e in errs), f"缺少“无法识别工艺路线格式”通用错误：{errs!r}"


