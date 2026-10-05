"""Template parsing reuses decoded route text and concrete repository facts."""

import sqlite3
from types import SimpleNamespace

import pytest

from core.errors import BusinessError
from core.services.process.part_service import PartService
from core.services.process.route_parser import RouteParser
from data.repositories.op_type_repo import OpTypeRepository
from data.repositories.supplier_repo import SupplierRepository


@pytest.mark.parametrize("route", ["5热处理", "5: 热处理"])
def test_template_format_and_full_parse_decode_original_once(monkeypatch, route):
    operation = SimpleNamespace(op_type_id="EXT", name="热处理", category="external")
    op_repo = SimpleNamespace(list=lambda: [operation], get=lambda key: operation)
    parser = RouteParser(op_repo, SimpleNamespace(list=lambda: []))
    original, calls = parser._read_route_input, []

    def read(text, errors):
        calls.append(text)
        return original(text, errors)

    monkeypatch.setattr(parser, "_read_route_input", read)
    service = PartService.__new__(PartService)
    service.route_parser = parser
    result = service._parse_route_or_raise(part_no="P", route_raw=route)
    assert len(result.operations) == 1 and calls == [route]
    with pytest.raises(BusinessError, match="必须以工序号开头"):
        service._parse_route_or_raise(part_no="P", route_raw="ABC5")


def test_concrete_parser_context_reads_all_work_types_once():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE OpTypes(op_type_id TEXT,name TEXT,category TEXT,default_hours REAL,remark TEXT,created_at TEXT);
            INSERT INTO OpTypes VALUES ('EXT','热处理','external',NULL,NULL,NULL);
            CREATE TABLE Suppliers(supplier_id TEXT,op_type_id TEXT,status TEXT,default_days REAL);
            CREATE TABLE WorkbenchSupplierOpTypes(supplier_id TEXT,op_type_id TEXT);
        """)
        conn.executemany("INSERT INTO Suppliers VALUES (?, 'EXT', 'active', 2)", [("S" + str(n),) for n in range(8)])
        conn.commit()
        statements = []
        conn.set_trace_callback(statements.append)
        result = RouteParser(OpTypeRepository(conn), SupplierRepository(conn)).parse("5热处理", "P", strict_mode=True)
        assert result.operations[0].supplier_id == "S7"
        assert result.operations[0].default_days == 2
        assert sum("FROM OpTypes" in statement for statement in statements) == 1
        assert statements[0] == "BEGIN" and statements[-1] == "COMMIT"
        assert not conn.in_transaction
    finally:
        conn.close()
