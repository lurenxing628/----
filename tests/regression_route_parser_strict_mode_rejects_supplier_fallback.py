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
class _Supplier:
    supplier_id: str
    op_type_id: str
    default_days: float


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

    op_repo = _StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")])

    parser_missing = RouteParser(
        op_types_repo=op_repo,
        suppliers_repo=_StubSuppliersRepo(suppliers=[]),
        logger=None,
    )
    result_missing = parser_missing.parse("5表处理", part_no="P_STRICT_NO_SUP", strict_mode=True)
    assert result_missing.status in (ParseStatus.FAILED, ParseStatus.FAILED.value), (
        f"strict_mode 缺供应商映射应失败：{result_missing.status!r}"
    )
    assert any("未找到供应商配置" in str(msg) and "严格模式" in str(msg) for msg in (result_missing.errors or [])), (
        f"strict_mode 缺供应商错误未透出：{result_missing.errors!r}"
    )

    parser_invalid = RouteParser(
        op_types_repo=op_repo,
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_ZERO", op_type_id="OT_EXT", default_days=0.0)]),
        logger=None,
    )
    result_invalid = parser_invalid.parse("5表处理", part_no="P_STRICT_BAD_DAYS", strict_mode=True)
    assert result_invalid.status in (ParseStatus.FAILED, ParseStatus.FAILED.value), (
        f"strict_mode default_days=0 应失败：{result_invalid.status!r}"
    )
    assert any("严格模式已拒绝按 1.0 天处理" in str(msg) for msg in (result_invalid.errors or [])), (
        f"strict_mode 默认周期错误未透出：{result_invalid.errors!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
