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
class _RaisingGetOpTypesRepo:
    op_types: List[_OpType]

    def list(self):
        return list(self.op_types)

    def get(self, _op_type_id: str):
        raise RuntimeError("op type repo boom")


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
        f"strict_mode 缺可用外协供应商应失败：{result_missing.status!r}"
    )
    assert any("没有可用的外协供应商" in str(msg) and "已开启严格校验" in str(msg) for msg in (result_missing.errors or [])), (
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
    assert any("已开启严格校验，请先把这个周期补正确" in str(msg) for msg in (result_invalid.errors or [])), (
        f"strict_mode 默认周期错误未透出：{result_invalid.errors!r}"
    )

    parser_mapping_failed_relaxed = RouteParser(
        op_types_repo=_RaisingGetOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_BAD_MAP", op_type_id="OT_EXT", default_days=1.0)]),
        logger=None,
    )
    result_mapping_failed_relaxed = parser_mapping_failed_relaxed.parse("5表处理", part_no="P_SUP_MAP_WARN", strict_mode=False)
    assert result_mapping_failed_relaxed.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), (
        f"供应商工种映射失败 relaxed 应为 partial：{result_mapping_failed_relaxed.status!r}"
    )
    assert any("工种映射加载失败" in str(msg) for msg in (result_mapping_failed_relaxed.warnings or [])), (
        f"供应商工种映射失败 warning 未透出：{result_mapping_failed_relaxed.warnings!r}"
    )

    parser_mapping_failed_strict = RouteParser(
        op_types_repo=_RaisingGetOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_BAD_MAP", op_type_id="OT_EXT", default_days=1.0)]),
        logger=None,
    )
    result_mapping_failed_strict = parser_mapping_failed_strict.parse("5表处理", part_no="P_SUP_MAP_ERR", strict_mode=True)
    assert result_mapping_failed_strict.status in (ParseStatus.FAILED, ParseStatus.FAILED.value), (
        f"供应商工种映射失败 strict 应失败：{result_mapping_failed_strict.status!r}"
    )
    assert any("工种映射加载失败" in str(msg) for msg in (result_mapping_failed_strict.errors or [])), (
        f"供应商工种映射失败 error 未透出：{result_mapping_failed_strict.errors!r}"
    )

    parser_mapping_missing_relaxed = RouteParser(
        op_types_repo=op_repo,
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_STALE_MAP", op_type_id="OT_MISSING", default_days=1.0)]),
        logger=None,
    )
    result_mapping_missing_relaxed = parser_mapping_missing_relaxed.parse("5表处理", part_no="P_SUP_MAP_MISSING_WARN", strict_mode=False)
    assert result_mapping_missing_relaxed.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), (
        f"供应商工种指向不存在 relaxed 应为 partial：{result_mapping_missing_relaxed.status!r}"
    )
    assert any("工种映射加载失败" in str(msg) and "没有找到对应工种" in str(msg) for msg in (result_mapping_missing_relaxed.warnings or [])), (
        f"供应商工种指向不存在 warning 未透出：{result_mapping_missing_relaxed.warnings!r}"
    )

    parser_mapping_missing_strict = RouteParser(
        op_types_repo=op_repo,
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_STALE_MAP", op_type_id="OT_MISSING", default_days=1.0)]),
        logger=None,
    )
    result_mapping_missing_strict = parser_mapping_missing_strict.parse("5表处理", part_no="P_SUP_MAP_MISSING_ERR", strict_mode=True)
    assert result_mapping_missing_strict.status in (ParseStatus.FAILED, ParseStatus.FAILED.value), (
        f"供应商工种指向不存在 strict 应失败：{result_mapping_missing_strict.status!r}"
    )
    assert any("工种映射加载失败" in str(msg) and "没有找到对应工种" in str(msg) for msg in (result_mapping_missing_strict.errors or [])), (
        f"供应商工种指向不存在 error 未透出：{result_mapping_missing_strict.errors!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
