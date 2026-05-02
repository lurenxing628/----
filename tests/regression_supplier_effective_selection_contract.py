from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import List

from core.services.process.part_service import PartService
from core.services.process.route_parser import ParseStatus, RouteParser


@dataclass
class _OpType:
    op_type_id: str
    name: str
    category: str | None


@dataclass
class _Supplier:
    supplier_id: str
    op_type_id: str
    default_days: float | str | None
    status: str = "active"


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
    suppliers: List[_Supplier]

    def list(self, status: str | None = None):
        rows = list(self.suppliers)
        if status is None:
            return rows
        expected = str(status or "").strip().lower()
        return [item for item in rows if str(getattr(item, "status", "") or "").strip().lower() == expected]


class _SnapshotService(PartService):
    def __init__(self, parser: RouteParser) -> None:
        self._parser = parser

    def parse(self, route_raw, part_no: str, *, strict_mode: bool = False):
        return self._parser.parse(str(route_raw or ""), part_no=part_no, strict_mode=bool(strict_mode))


def test_part_service_route_parse_baseline_snapshot_uses_highest_supplier_id_as_effective_supplier() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_A", op_type_id="OT_EXT", default_days=2.0),
                _Supplier(supplier_id="SUP_Z", op_type_id="OT_EXT", default_days=5.0),
                _Supplier(supplier_id="SUP_M", op_type_id="OT_EXT", default_days=3.0),
            ]
        ),
        logger=None,
    )
    svc = _SnapshotService(parser)

    snapshot = svc.build_route_parse_baseline_snapshot(
        part_nos=["P_EFFECTIVE_SUP"],
        parts_cache={"P_EFFECTIVE_SUP": SimpleNamespace(route_raw="10表处理")},
    )

    assert snapshot == [
        {
            "part_no": "P_EFFECTIVE_SUP",
            "route_op_types": [{"name": "表处理", "matched_op_type_id": "OT_EXT", "source": "external"}],
            "suppliers": [
                {
                    "supplier_id": "SUP_Z",
                    "op_type_id": "OT_EXT",
                    "op_type_name": "表处理",
                    "default_days": 5.0,
                }
            ],
        }
    ]


def test_part_service_route_parse_baseline_snapshot_treats_blank_category_as_internal() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category=None)]),
        suppliers_repo=_StubSuppliersRepo(suppliers=[_Supplier(supplier_id="SUP1", op_type_id="OT_EXT", default_days=2.0)]),
        logger=None,
    )
    svc = _SnapshotService(parser)

    snapshot = svc.build_route_parse_baseline_snapshot(
        part_nos=["P_BLANK_CATEGORY"],
        parts_cache={"P_BLANK_CATEGORY": SimpleNamespace(route_raw="10表处理")},
    )

    assert snapshot == [
        {
            "part_no": "P_BLANK_CATEGORY",
            "route_op_types": [{"name": "表处理", "matched_op_type_id": "OT_EXT", "source": "internal"}],
            "suppliers": [],
        }
    ]


def test_route_parser_uses_highest_supplier_id_as_effective_supplier() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_A", op_type_id="OT_EXT", default_days=2.0),
                _Supplier(supplier_id="SUP_Z", op_type_id="OT_EXT", default_days=5.0),
                _Supplier(supplier_id="SUP_M", op_type_id="OT_EXT", default_days=3.0),
            ]
        ),
        logger=None,
    )

    supplier_map, issues = parser._build_supplier_map()

    assert supplier_map == {"表处理": ("SUP_Z", 5.0)}
    assert issues == {}


def test_route_parser_only_uses_active_suppliers_for_effective_supplier() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_A", op_type_id="OT_EXT", default_days=2.0, status="active"),
                _Supplier(supplier_id="SUP_Z", op_type_id="OT_EXT", default_days=5.0, status="inactive"),
            ]
        ),
        logger=None,
    )

    supplier_map, issues = parser._build_supplier_map()
    result = parser.parse("10表处理", part_no="P_ACTIVE_SUPPLIER", strict_mode=True)

    assert supplier_map == {"表处理": ("SUP_A", 2.0)}
    assert issues == {}
    assert result.status == ParseStatus.SUCCESS
    assert result.operations[0].supplier_id == "SUP_A"
    assert result.operations[0].default_days == 2.0


def test_route_parser_treats_inactive_only_supplier_as_missing_supplier() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_INACTIVE", op_type_id="OT_EXT", default_days=5.0, status="inactive"),
            ]
        ),
        logger=None,
    )

    relaxed = parser.parse("10表处理", part_no="P_INACTIVE_ONLY", strict_mode=False)
    strict = parser.parse("10表处理", part_no="P_INACTIVE_ONLY", strict_mode=True)

    assert relaxed.status == ParseStatus.PARTIAL
    assert relaxed.operations[0].supplier_id is None
    assert relaxed.operations[0].default_days == 1.0
    assert any("没有找到可用的外协供应商" in str(msg) for msg in relaxed.warnings)

    assert strict.status == ParseStatus.FAILED
    assert any("没有可用的外协供应商" in str(msg) for msg in strict.errors)


def test_route_parser_ignores_stale_issue_from_non_effective_supplier() -> None:
    parser = RouteParser(
        op_types_repo=_StubOpTypesRepo(op_types=[_OpType(op_type_id="OT_EXT", name="表处理", category="external")]),
        suppliers_repo=_StubSuppliersRepo(
            suppliers=[
                _Supplier(supplier_id="SUP_A", op_type_id="OT_EXT", default_days=""),
                _Supplier(supplier_id="SUP_Z", op_type_id="OT_EXT", default_days=5.0),
            ]
        ),
        logger=None,
    )

    supplier_map, issues = parser._build_supplier_map()
    result = parser.parse("10表处理", part_no="P_EFFECTIVE_SUP", strict_mode=True)

    assert supplier_map == {"表处理": ("SUP_Z", 5.0)}
    assert issues == {}
    assert result.status == ParseStatus.SUCCESS
    assert result.errors == []
    assert result.warnings == []
    assert len(result.operations) == 1
    assert result.operations[0].supplier_id == "SUP_Z"
    assert result.operations[0].default_days == 5.0
