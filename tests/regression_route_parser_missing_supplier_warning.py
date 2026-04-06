import os
import sys
from dataclasses import dataclass
from typing import List


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process.route_parser import ParseStatus, RouteParser

    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(suppliers=[]),
        logger=None,
    )
    result = parser.parse("5表处理", part_no="P_NO_SUP")

    assert result.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), f"缺供应商映射应返回 PARTIAL：{result.status!r}"
    assert len(result.operations or []) == 1, f"外部工序解析数量异常：{result.operations!r}"

    op = result.operations[0]
    assert str(op.source or "").strip().lower() == "external", f"工序来源异常：{op.source!r}"
    assert abs(float(op.default_days or 0.0) - 1.0) < 1e-9, f"默认周期未回退为 1.0：{op.default_days!r}"
    assert any("未找到供应商配置" in str(msg) for msg in (result.warnings or [])), f"未透出缺供应商 warning：{result.warnings!r}"

    print("OK")


if __name__ == "__main__":
    main()
