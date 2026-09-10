"""Real route parsing over the legacy/explicit supplier capability union."""

import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.errors import AppError, BusinessError, ErrorCode
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.process.part_service import PartService
from core.services.process.route_parser import ParseStatus, RouteParser
from core.services.process.route_parser_constraints import SupplierConstraintResolver
from core.services.process.supplier_service import SupplierService
from core.services.workbench.suppliers import WorkbenchSupplierService
from data.repositories.op_type_repo import OpTypeRepository
from data.repositories.supplier_repo import SupplierRepository
from tests.workbench.supplier_support import (
    CREATE,
    KEY,
    identity_for,
    relationships,
    run_supplier,
    stored_state,
    supplier_database,
    supplier_row,
)


def parser(conn):
    return RouteParser(OpTypeRepository(conn), SupplierRepository(conn))


def test_create_multiskill_supplier_then_real_route_parse_and_capability_removal(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "relationships": relationships(conn, "HEAT", "COAT")})
    route_parser = parser(conn)
    parsed = route_parser.parse("10热处理-20表处理", part_no="P", strict_mode=True)
    assert parsed.status == ParseStatus.SUCCESS
    assert [(op.supplier_id, op.default_days, op.source) for op in parsed.operations] == [("SUP2", 2.5, "external")] * 2
    assert not parsed.warnings and not parsed.errors
    run_supplier(conn, "update", {"relationships": relationships(conn, "HEAT")},
                 identity=identity_for(conn, "SUP2"), key=KEY + "-remove")
    after = route_parser.parse("10热处理-20表处理", part_no="P", strict_mode=True)
    assert after.status == ParseStatus.FAILED
    assert after.operations[0].supplier_id == "SUP2"
    assert after.operations[1].supplier_id is None
    assert any("没有可用的外协供应商" in error for error in after.errors)


def test_pending_review_and_disabled_are_never_candidates(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "relationships": relationships(conn, "HEAT", "COAT"),
        "fields": {"default_days": 4, "status": "pending_review"}})
    assert supplier_row(conn, "SUP2")["status"] == "inactive"
    assert SupplierRepository(conn).list_capabilities("active") == [
        {"supplier_id": "SUP1", "op_type_id": "HEAT", "default_days": 3.5, "status": "active", "explicit": 0, "missing_supplier": 0}]
    for index, status in enumerate(("pending_review", "inactive", "active")):
        run_supplier(conn, "update", {"fields": {"status": status}}, identity=identity_for(conn, "SUP2"), key=KEY + str(index))
        result = parser(conn).parse("10表处理", part_no="P", strict_mode=True)
        assert result.status == (ParseStatus.SUCCESS if status == "active" else ParseStatus.FAILED)


def test_primary_duplicate_is_deduped_without_touching_old_list_get_or_revision(supplier_conn):
    conn = supplier_conn
    repo = SupplierRepository(conn)
    old_list, old_get = repo.list(), repo.get("SUP1")
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes VALUES ('SUP1', ?)", [("HEAT",), ("COAT",)])
    conn.commit()
    capabilities = repo.list_capabilities("active")
    assert [row["op_type_id"] for row in capabilities] == ["COAT", "HEAT"]
    assert repo.list() == old_list and repo.get("SUP1") == old_get
    identity = identity_for(conn)
    outcome = run_supplier(conn, "update", {"relationships": relationships(conn, "HEAT", "COAT")})
    assert outcome["result"] == "unchanged" and identity_for(conn) == identity
    assert parser(conn)._build_supplier_map() == ({"热处理": ("SUP1", 3.5), "表处理": ("SUP1", 3.5)}, {})


def test_legacy_only_source_parse_and_baseline_are_identical(supplier_conn):
    conn = supplier_conn
    conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('UNBOUND','No guessed skills',4)")
    conn.commit()
    repo = SupplierRepository(conn)
    legacy = RouteParser(OpTypeRepository(conn), SimpleNamespace(list=repo.list))
    actual = parser(conn)
    route = "10数铣-20热处理"
    assert actual.parse(route, part_no="P", strict_mode=True).to_dict() == legacy.parse(route, part_no="P", strict_mode=True).to_dict()
    assert len(repo.list_capabilities()) == 1
    service = PartService(conn)
    assert service.build_route_parse_baseline_snapshot(part_nos=["P"], parts_cache={"P": SimpleNamespace(route_raw=route)}) == [
        {"part_no": "P", "route_op_types": [
            {"name": "数铣", "matched_op_type_id": "MILL", "source": "internal"},
            {"name": "热处理", "matched_op_type_id": "HEAT", "source": "external"}],
         "suppliers": [{"supplier_id": "SUP1", "op_type_id": "HEAT", "op_type_name": "热处理", "default_days": 3.5}]}]


def test_supplier_id_order_and_winner_issues_remain_consistent(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "business_code": "SUP_Z", "relationships": relationships(conn, "HEAT", "COAT")})
    conn.execute("UPDATE Suppliers SET default_days = '' WHERE supplier_id = 'SUP1'")
    conn.commit()
    result = parser(conn).parse("10热处理-20表处理", part_no="P", strict_mode=True)
    assert result.status == ParseStatus.SUCCESS and not result.warnings
    assert all(op.supplier_id == "SUP_Z" for op in result.operations)


@pytest.mark.parametrize("days,warning", [(None, "默认周期为空"), ("", "默认周期为空"), ("bad", "默认周期格式不正确"), (0, "默认周期无效"), (-1, "默认周期无效"), (float("inf"), "默认周期无效")])
def test_raw_invalid_cycle_is_visible_per_capability_and_strict_rejects(supplier_conn, days, warning):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "relationships": relationships(conn, "HEAT", "COAT")})
    conn.execute("UPDATE Suppliers SET default_days = ? WHERE supplier_id = 'SUP2'", (days,))
    conn.commit()
    rows = [row for row in SupplierRepository(conn).list_capabilities("active") if row["supplier_id"] == "SUP2"]
    assert len(rows) == 2 and all(row["default_days"] == days for row in rows)
    relaxed = parser(conn).parse("10热处理-20表处理", part_no="P")
    strict = parser(conn).parse("10热处理-20表处理", part_no="P", strict_mode=True)
    assert relaxed.status == ParseStatus.PARTIAL and strict.status == ParseStatus.FAILED
    assert all(op.default_days == 1.0 for op in relaxed.operations)
    assert any(warning in message for message in relaxed.warnings)
    assert strict.errors


@pytest.mark.parametrize("supplier,op_type", [("SUP1", "MISSING"), ("SUP1", "MILL"), ("SUP1", ""), ("MISSING", "COAT")])
def test_bad_explicit_relationship_is_visible_and_global_issue_scope_is_preserved(supplier_conn, supplier, op_type):
    conn = supplier_conn
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes VALUES (?, ?)", (supplier, op_type))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    resolver = SupplierConstraintResolver(OpTypeRepository(conn), SupplierRepository(conn))
    mapping, _ = resolver.build_supplier_map()
    assert mapping == {"热处理": ("SUP1", 3.5)}
    assert len(resolver.global_issues) == 1 and resolver.global_issues[0].op_type_id == op_type
    result = parser(conn).parse("10热处理", part_no="P", strict_mode=True)
    assert result.status == ParseStatus.PARTIAL and result.errors == []
    assert any("工种映射加载失败" in message for message in result.warnings)


def test_missing_table_production_typeerror_and_bad_projection_never_fall_back(supplier_conn):
    conn = supplier_conn
    conn.execute("DROP TABLE WorkbenchSupplierOpTypes")
    conn.commit()
    with patch.object(SupplierRepository, "list", side_effect=AssertionError("must not fall back")):
        with pytest.raises(AppError) as raised:
            parser(conn).build_parse_context()
    assert isinstance(raised.value.cause, sqlite3.OperationalError)
    with patch.object(SupplierRepository, "list_capabilities", side_effect=TypeError("production bug")):
        with pytest.raises(TypeError, match="production bug"):
            parser(conn).build_parse_context()


def test_legacy_fake_signature_adaptation_does_not_swallow_execution_typeerror(supplier_conn):
    conn = supplier_conn
    repo = SupplierRepository(conn)
    fake = SimpleNamespace(list=lambda: repo.list())
    assert RouteParser(OpTypeRepository(conn), fake)._build_supplier_map() == ({"热处理": ("SUP1", 3.5)}, {})

    def broken(status=None):
        raise TypeError("fake implementation error")

    with pytest.raises(TypeError, match="fake implementation error"):
        RouteParser(OpTypeRepository(conn), SimpleNamespace(list=broken)).build_parse_context()


@pytest.mark.parametrize("relation", ("part", "batch", "group"))
def test_real_references_guard_snapshot_and_domain_delete_preserve_everything(supplier_conn, relation):
    conn = supplier_conn
    adapter, identity = WorkbenchSupplierService(conn), identity_for(conn)
    before = adapter.snapshot(identity)
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P','Part')")
    if relation == "part":
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,supplier_id) VALUES ('P',10,'Heat','SUP1')")
    elif relation == "batch":
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B','P',1)")
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,supplier_id) VALUES ('B10','B',10,'Heat','SUP1')")
    else:
        conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,supplier_id) VALUES ('G','P',10,20,'SUP1')")
    conn.commit()
    assert input_fingerprint(adapter.snapshot(identity_for(conn))) != input_fingerprint(before)
    stored = stored_state(conn)
    with pytest.raises(BusinessError) as raised:
        run_supplier(conn, "delete", {})
    assert raised.value.code == ErrorCode.PERMISSION_DENIED and stored_state(conn) == stored
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_fk_backstop_and_op_type_fk_protect_relationships(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "update", {"relationships": relationships(conn, "HEAT", "COAT")})
    stored = stored_state(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM OpTypes WHERE op_type_id = 'COAT'")
    conn.rollback()
    assert stored_state(conn) == stored
    conn.execute("CREATE TABLE TestSupplierReferences(supplier_id TEXT REFERENCES Suppliers(supplier_id))")
    conn.execute("INSERT INTO TestSupplierReferences VALUES ('SUP1')")
    conn.commit()
    stored = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as raised:
        run_supplier(conn, "delete", {}, key=KEY + "-delete")
    assert raised.value.code == "constraint_conflict" and stored_state(conn) == stored
