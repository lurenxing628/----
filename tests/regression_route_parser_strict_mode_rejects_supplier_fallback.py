"""回归测试：RouteParser strict_mode 对外协供应商缺失/失效的拦截边界——外协工序无可用供应商或 default_days=0 时严格模式判 FAILED 并透出可读错误；
供应商工种映射加载失败 relaxed 降为 PARTIAL 仅告警、strict 则 FAILED；但与当前路线无关的脏供应商映射只作 warning，不得把纯内部路线或已满足供应商的外协路线误卡成失败。"""

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
    mixed_op_repo = _StubOpTypesRepo(
        op_types=[
            _OpType(op_type_id="OT_INTERNAL", name="数铣", category="internal"),
            _OpType(op_type_id="OT_EXT", name="表处理", category="external"),
        ]
    )

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
    assert any("没有可用的外协供应商" in str(msg) and "表处理" in str(msg) for msg in (result_mapping_missing_strict.errors or [])), (
        f"当前路线引用的外协工序缺供应商错误未透出：{result_mapping_missing_strict.errors!r}"
    )
    assert not any("工种映射加载失败" in str(msg) and "没有找到对应工种" in str(msg) for msg in (result_mapping_missing_strict.errors or [])), (
        f"无关供应商脏映射不应作为 strict error 拦截当前路线：{result_mapping_missing_strict.errors!r}"
    )
    assert any("工种映射加载失败" in str(msg) and "没有找到对应工种" in str(msg) for msg in (result_mapping_missing_strict.warnings or [])), (
        f"无关供应商脏映射仍应作为 warning 透出：{result_mapping_missing_strict.warnings!r}"
    )

    parser_internal_with_stale_supplier = RouteParser(
        op_types_repo=mixed_op_repo,
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP_STALE_UNRELATED", op_type_id="OT_MISSING", default_days=1.0)]),
        logger=None,
    )
    result_internal = parser_internal_with_stale_supplier.parse("5数铣", part_no="P_INTERNAL_ONLY", strict_mode=True)
    assert result_internal.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), (
        f"内部路线不应被无关供应商脏映射卡成失败：{result_internal.status!r} errors={result_internal.errors!r}"
    )
    assert result_internal.errors == [], f"内部路线不应产生 strict error：{result_internal.errors!r}"
    assert result_internal.stats.get("internal") == 1 and result_internal.stats.get("external") == 0, (
        f"内部路线统计异常：{result_internal.stats!r}"
    )
    assert any("工种映射加载失败" in str(msg) for msg in (result_internal.warnings or [])), (
        f"无关供应商脏映射应作为 warning 透出：{result_internal.warnings!r}"
    )

    parser_external_with_stale_unreferenced_supplier = RouteParser(
        op_types_repo=mixed_op_repo,
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_OK", op_type_id="OT_EXT", default_days=2.0),
                _Supplier(supplier_id="SUP_STALE_UNRELATED", op_type_id="OT_MISSING", default_days=1.0),
            ]
        ),
        logger=None,
    )
    result_external = parser_external_with_stale_unreferenced_supplier.parse("5表处理", part_no="P_EXT_WITH_STALE_OTHER", strict_mode=True)
    assert result_external.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), (
        f"已满足供应商的外协路线不应被无关供应商脏映射卡成失败：{result_external.status!r} errors={result_external.errors!r}"
    )
    assert result_external.errors == [], f"无关供应商脏映射不应产生 strict error：{result_external.errors!r}"
    assert result_external.operations[0].supplier_id == "SUP_OK", f"有效供应商未正常匹配：{result_external.operations[0].to_dict()!r}"
    assert result_external.operations[0].default_days == 2.0, f"有效供应商周期未正常使用：{result_external.operations[0].to_dict()!r}"
    assert any("工种映射加载失败" in str(msg) for msg in (result_external.warnings or [])), (
        f"无关供应商脏映射应作为 warning 透出：{result_external.warnings!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
