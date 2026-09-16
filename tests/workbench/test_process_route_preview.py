"""Route preview contracts against real temporary schema, parser and v21 capabilities."""

import json
import sqlite3
from datetime import date
from unittest.mock import patch

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import MAX_ROUTE_SEQUENCE, MAX_ROUTE_TEXT_BYTES
from core.services.process.part_service import PartService
from core.services.process.route_parser import RouteParser
from core.services.workbench.process_route_preview import ProcessRoutePreviewService
from data.repositories.op_type_repo import OpTypeRepository
from data.repositories.supplier_repo import SupplierRepository
from tests.workbench.process_route_support import (
    all_table_snapshot,
    preview,
    raw_ref,
    read_only_probe,
    route_database,
    seed_scale,
    typed_route_database,
)


@pytest.mark.parametrize("text", ["10数铣20热处理30表处理", "10 数铣 20 热处理 30 表处理",
                                  "10数铣\n20热处理\n30表处理", "10数铣,20热处理，30表处理",
                                  "10数铣;20热处理；30表处理", "１０数铣 -> ２０热处理 → ３０表处理"])
def test_text_variants_use_real_op_types_and_v21_capabilities(route_conn, text):
    result = preview(route_conn, text)
    assert result["can_confirm_route"] is True
    assert result["route_raw"] == text and result["normalized_input"] == "10数铣20热处理30表处理"
    assert result["counts"] == {"operations": 3, "recognized": 3, "unknown": 0}
    assert [(op["sequence"], op["source_suggestion"], op["external_days"]) for op in result["operations"]] == [
        (10, "internal", None), (20, "external", 3.75), (30, "external", 3.75)]
    for op, key in zip(result["operations"], ("MILL", "HEAT", "COAT")):
        assert op["op_type_ref"] == raw_ref(route_conn, "op_type", key)
        if key != "MILL":
            assert op["supplier_ref"] == raw_ref(route_conn, "supplier", "SUP-Z")
            assert op["supplier_label"] == "多能力供应商"
    assert "multiple_supplier_candidates" in {d["code"] for d in result["diagnostics"]}
    assert result["operations"][0]["basis"] == "按工种类别匹配；可在归属步骤修改。"
    assert result["operations"][1]["basis"] == "按工种类别匹配；可在归属步骤修改。供应商按编号排序选择最后一家。"
    assert result["operations"][2]["basis"] == "按工种类别匹配；可在归属步骤修改。"
    multiple = next(item for item in result["operations"][1]["issues"] if item["code"] == "multiple_supplier_candidates")
    assert multiple["message"] == "有 2 家供应商可承接，可在归属步骤改选。"
    json.dumps(result, allow_nan=False)


def test_rows_are_sorted_without_mutation_and_match_text(route_conn):
    body = {"mode": "rows", "rows": [{"seq": 20, "op_type_name": "热处理"}, {"seq": 10, "op_type_name": "数铣"}]}
    original = json.dumps(body)
    rows = ProcessRoutePreviewService(route_conn).preview(body)
    assert rows["operations"] == preview(route_conn, "10数铣20热处理")["operations"]
    assert json.dumps(body) == original and rows["mode"] == "rows" and rows["can_confirm_route"]


def test_unknown_is_not_external_and_only_route_can_be_confirmed(route_conn):
    result = preview(route_conn, "10未建工种20数铣")
    op = result["operations"][0]
    assert result["can_confirm_route"] and result["counts"] == {"operations": 2, "recognized": 1, "unknown": 1}
    assert all(op[key] is None for key in ("op_type_ref", "source_suggestion", "supplier_ref", "supplier_label", "external_days"))
    assert op["issues"][0]["code"] == "unknown_op_type"
    assert all(item["severity"] == "warning" for item in result["diagnostics"])


@pytest.mark.parametrize("body", [
    {"mode": "text", "route_raw": "10数铣10热处理20表处理"},
    {"mode": "rows", "rows": [{"seq": 10, "op_type_name": "数铣"}, {"seq": 10, "op_type_name": "热处理"}, {"seq": 20, "op_type_name": "表处理"}]},
])
def test_duplicates_are_errors_and_neither_occurrence_is_silently_dropped(route_conn, body):
    result = ProcessRoutePreviewService(route_conn).preview(body)
    assert not result["can_confirm_route"] and len(result["operations"]) == 3
    assert {d["sequence"] for d in result["diagnostics"] if d["code"] == "duplicate_sequence"} == {10}
    for op in result["operations"][:2]:
        assert any(issue["code"] == "duplicate_sequence" for issue in op["issues"])


@pytest.mark.parametrize("text,code", [("10数铣20", "missing_operation_name"), ("10数铣;20;30表处理", "missing_operation_name"),
    ("无编号;10数铣20热处理", "missing_sequence"), ("0数铣20热处理", "invalid_sequence"),
    ("-10数铣20热处理", "ambiguous_route_format"), ("1.5数铣20热处理", "ambiguous_route_format"),
    ("1e2数铣20热处理", "ambiguous_route_format"), ("10 20数铣30热处理", "ambiguous_route_format"),
    ("10数 铣20热处理", "ambiguous_route_format"), (str(MAX_ROUTE_SEQUENCE + 1) + "数铣20热处理", "invalid_sequence")])
def test_parse_errors_keep_diagnostics_and_remaining_preview(route_conn, text, code):
    result = preview(route_conn, text)
    assert not result["can_confirm_route"]
    assert code in {item["code"] for item in result["diagnostics"] if item["severity"] == "error"}
    assert result["operations"]


def test_independent_errors_are_all_visible(route_conn):
    result = preview(route_conn, "无编号;0数铣;10数铣;10热处理;20;30表处理")
    codes = {item["code"] for item in result["diagnostics"]}
    assert {"missing_sequence", "invalid_sequence", "duplicate_sequence", "missing_operation_name"} <= codes
    assert result["operations"][-1]["sequence"] == 30


@pytest.mark.parametrize("body", [None, [], True, {}, {"mode": []}, {"mode": "bogus"}, {"mode": "text"},
    {"mode": "text", "route_raw": "10数铣", "unknown": 1}, {"mode": "rows", "rows": [], "route_raw": ""},
    {"mode": "rows", "rows": [{"seq": 1, "op_type_name": "数铣", "source": "external"}]}])
def test_invalid_object_contract_raises_400_without_database_access(route_conn, body):
    with read_only_probe(route_conn) as statements:
        with pytest.raises(WorkbenchCommandRejected) as failure:
            ProcessRoutePreviewService(route_conn).preview(body)
    assert failure.value.status == 400 and statements == []


@pytest.mark.parametrize("seq", [True, False, None, "1", 1.0, 1.5, float("nan"), float("inf"), -float("inf"), [], {}])
def test_non_integer_or_boolean_sequence_is_not_coerced(route_conn, seq):
    with pytest.raises(WorkbenchCommandRejected) as failure:
        ProcessRoutePreviewService(route_conn).preview({"mode": "rows", "rows": [{"seq": seq, "op_type_name": "数铣"}]})
    assert failure.value.status == 422


@pytest.mark.parametrize("body", [{"mode": "text", "route_raw": None}, {"mode": "text", "route_raw": "\ud800"},
    {"mode": "rows", "rows": {}}, {"mode": "rows", "rows": [{"seq": 1, "op_type_name": None}]}])
def test_invalid_value_contract_is_422(route_conn, body):
    with pytest.raises(WorkbenchCommandRejected) as failure:
        ProcessRoutePreviewService(route_conn).preview(body)
    assert failure.value.status == 422


@pytest.mark.parametrize("seq", [0, -1, MAX_ROUTE_SEQUENCE + 1, 10 ** 5000])
def test_invalid_integer_rows_keep_other_valid_rows(route_conn, seq):
    result = ProcessRoutePreviewService(route_conn).preview({"mode": "rows", "rows": [
        {"seq": seq, "op_type_name": "数铣"}, {"seq": 20, "op_type_name": "热处理"}]})
    assert not result["can_confirm_route"] and [op["sequence"] for op in result["operations"]] == [20]


@pytest.mark.parametrize("body", [{"mode": "text", "route_raw": ""}, {"mode": "text", "route_raw": " ; , \n"},
    {"mode": "rows", "rows": []}, {"mode": "rows", "rows": [{"seq": 1, "op_type_name": " "}]}])
def test_empty_input_is_an_error_not_a_valid_route(route_conn, body):
    result = ProcessRoutePreviewService(route_conn).preview(body)
    assert not result["can_confirm_route"] and result["diagnostics"] and not result["operations"]


@pytest.mark.parametrize("days", [None, "", "bad", 0, -1, float("inf"), float("nan")])
def test_invalid_real_cycle_stays_null_never_one_day(route_conn, days):
    route_conn.execute("UPDATE Suppliers SET default_days=? WHERE supplier_id='SUP-Z'", (days,))
    route_conn.commit()
    result = preview(route_conn, "10热处理20表处理30无供应商工种")
    assert result["can_confirm_route"]
    assert all(op["external_days"] is None for op in result["operations"])
    assert all(any(i["code"] == "external_days_missing_or_invalid" for i in op["issues"]) for op in result["operations"][:2])
    assert result["operations"][2]["supplier_ref"] is None


@pytest.mark.parametrize("kind,key", [("op_type", "MILL"), ("supplier", "SUP-Z")])
@pytest.mark.parametrize("damage", ["missing", "inactive", "malformed"])
def test_persisted_identity_damage_fails_without_repair(route_conn, kind, key, damage):
    if damage == "missing":
        route_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=?", (kind, key))
    else:
        if damage == "malformed":
            route_conn.execute("PRAGMA ignore_check_constraints=ON")
        column, value = ("active", 0) if damage == "inactive" else ("ref", "bad-ref")
        route_conn.execute("UPDATE WorkbenchEntityRefs SET " + column + "=? WHERE kind=? AND entity_key=?", (value, kind, key))
    route_conn.commit()
    original = all_table_snapshot(route_conn)
    with read_only_probe(route_conn):
        with pytest.raises(WorkbenchCommandRejected) as failure:
            preview(route_conn, "10数铣20热处理")
    assert failure.value.code == "storage_failure" and failure.value.status == 500
    assert all_table_snapshot(route_conn) == original


def test_raw_invalid_category_is_not_normalized_to_internal(route_conn):
    route_conn.execute("PRAGMA ignore_check_constraints=ON")
    route_conn.execute("UPDATE OpTypes SET category='' WHERE op_type_id='MILL'")
    route_conn.commit()
    result = preview(route_conn, "10数铣")
    assert result["can_confirm_route"] and result["operations"][0]["source_suggestion"] is None
    assert result["operations"][0]["issues"][0]["code"] == "invalid_op_type_category"


@pytest.mark.parametrize("mode", ["text", "rows"])
def test_capacity_rejection_is_explicit_not_truncated(route_conn, mode):
    body = ({"mode": mode, "route_raw": ";".join(str(i + 1) + "数铣" for i in range(2001))} if mode == "text" else
            {"mode": mode, "rows": [{"seq": i + 1, "op_type_name": "数铣"} for i in range(2001)]})
    with read_only_probe(route_conn) as statements:
        with pytest.raises(WorkbenchCommandRejected) as failure:
            ProcessRoutePreviewService(route_conn).preview(body)
    assert failure.value.status == 413 and statements == []


def test_utf8_byte_boundary_and_huge_numeric_token(route_conn):
    exact = "1" + "a" * (MAX_ROUTE_TEXT_BYTES - 1)
    assert preview(route_conn, exact)["can_confirm_route"]
    for text in (exact + "a", "车" * (MAX_ROUTE_TEXT_BYTES // 3 + 1)):
        with pytest.raises(WorkbenchCommandRejected) as failure:
            preview(route_conn, text)
        assert failure.value.status == 413
    result = preview(route_conn, "9" * 5000 + "数铣20热处理")
    assert not result["can_confirm_route"] and result["operations"][0]["sequence"] == 20


def test_real_date_connection_all_tables_and_transaction_remain_unchanged(typed_route_conn):
    conn = typed_route_conn
    assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
    original, changes = all_table_snapshot(conn), conn.total_changes
    conn.execute("BEGIN")
    with read_only_probe(conn), patch.object(PartService, "reparse_and_save", side_effect=AssertionError("write path forbidden")):
        result = preview(conn, "10数铣20热处理30未知40")
    assert not result["can_confirm_route"] and conn.in_transaction and conn.total_changes == changes
    assert all_table_snapshot(conn) == original
    json.dumps(result, allow_nan=False)
    conn.rollback()


def test_preview_uses_current_reference_facts_not_cross_call_cache(route_conn):
    service = ProcessRoutePreviewService(route_conn)
    body = {"mode": "text", "route_raw": "10表处理"}
    assert service.preview(body)["operations"][0]["supplier_ref"]
    route_conn.execute("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='SUP-Z' AND op_type_id='COAT'")
    route_conn.commit()
    assert service.preview(body)["operations"][0]["supplier_ref"] is None


def test_formal_supplier_choice_and_no_n_plus_one_at_2000_distinct_capabilities(route_conn):
    rows = seed_scale(route_conn, 2000)
    changes = route_conn.total_changes
    with read_only_probe(route_conn) as statements, patch.object(OpTypeRepository, "get", side_effect=AssertionError("N+1")):
        result = ProcessRoutePreviewService(route_conn).preview({"mode": "rows", "rows": rows})
    assert result["can_confirm_route"] and result["counts"] == {"operations": 2000, "recognized": 2000, "unknown": 0}
    assert len(statements) == 11 and route_conn.total_changes == changes
    assert all(op["external_days"] == 2.25 for op in result["operations"])
    assert all(op["op_type_ref"] and op["supplier_ref"] for op in result["operations"])
    formal = RouteParser(OpTypeRepository(route_conn), SupplierRepository(route_conn)).parse("10热处理20表处理", "P", strict_mode=True)
    projected = preview(route_conn, "10热处理20表处理")
    assert [op["supplier_ref"] for op in projected["operations"]] == [raw_ref(route_conn, "supplier", op.supplier_id) for op in formal.operations]


def test_missing_v21_table_is_not_a_legacy_fallback(route_conn):
    from core.errors import AppError

    route_conn.execute("DROP TABLE WorkbenchSupplierOpTypes")
    route_conn.commit()
    with patch.object(SupplierRepository, "list", side_effect=AssertionError("legacy fallback forbidden")):
        with pytest.raises(AppError) as failure:
            preview(route_conn, "10数铣20热处理")
    assert isinstance(failure.value.cause, sqlite3.OperationalError)


@pytest.mark.parametrize("body", [
    {"mode": "text", "route_raw": "10数铣;10;20热处理"},
    {"mode": "rows", "rows": [{"seq": 10, "op_type_name": "数铣"}, {"seq": 10, "op_type_name": ""}, {"seq": 20, "op_type_name": "热处理"}]},
])
def test_missing_name_does_not_hide_duplicate_sequence(route_conn, body):
    result = ProcessRoutePreviewService(route_conn).preview(body)
    assert not result["can_confirm_route"]
    assert {"duplicate_sequence", "missing_operation_name"} <= {d["code"] for d in result["diagnostics"]}
    assert [op["sequence"] for op in result["operations"]] == [10, 20]


@pytest.mark.parametrize("name", ["数 铣", "工种二;新工种", "含3轴", "9" * (MAX_ROUTE_TEXT_BYTES - 1)])
def test_structured_row_name_is_preserved_without_text_reparsing(route_conn, name):
    result = ProcessRoutePreviewService(route_conn).preview({"mode": "rows", "rows": [{"seq": 1, "op_type_name": name}]})
    assert result["can_confirm_route"] and result["operations"][0]["op_type_name"] == name
    assert result["normalized_input"] == "1 " + name
    assert "structured_name_preserved" in {d["code"] for d in result["diagnostics"]}
    assert not any(d["severity"] == "error" for d in result["diagnostics"])


def test_max_length_numeric_text_is_bounded_and_invalid(route_conn):
    result = preview(route_conn, "9" * MAX_ROUTE_TEXT_BYTES)
    assert not result["can_confirm_route"] and not result["operations"]
    assert "invalid_sequence" in {d["code"] for d in result["diagnostics"]}


def test_exact_dto_keys_no_internal_ids_or_http_metadata(route_conn):
    result = preview(route_conn, "10数铣20热处理30未建工种")
    assert set(result) == {"mode", "route_raw", "normalized_input", "operations", "diagnostics", "can_confirm_route", "counts"}
    for op in result["operations"]:
        assert set(op) == {"sequence", "op_type_name", "op_type_ref", "source_suggestion", "supplier_ref", "supplier_label", "external_days", "basis", "issues"}
        assert type(op["basis"]) is str
        assert all(set(issue) == {"code", "message"} for issue in op["issues"])
    for item in result["diagnostics"]:
        assert set(item) <= {"code", "severity", "message", "sequence"}
        assert item["severity"] in ("error", "warning")
        assert type(item.get("sequence", 1)) is int


@pytest.mark.parametrize("supplier,op_type", [("SUP-Z", "MISSING"), ("SUP-Z", "MILL"), ("MISSING", "COAT")])
def test_bad_v21_capability_is_visible_without_leaking_internal_keys(route_conn, supplier, op_type):
    route_conn.execute("PRAGMA foreign_keys=OFF")
    route_conn.execute("INSERT INTO WorkbenchSupplierOpTypes VALUES (?,?)", (supplier, op_type))
    route_conn.commit()
    before = all_table_snapshot(route_conn)
    result = preview(route_conn, "10数铣20热处理")
    assert result["can_confirm_route"] and "supplier_capability_invalid" in {d["code"] for d in result["diagnostics"]}
    assert "MISSING" not in json.dumps(result) and "SUP-Z" not in json.dumps(result)
    assert all_table_snapshot(route_conn) == before


@pytest.mark.parametrize("mode", ["text", "rows"])
def test_exact_2000_operations_in_both_modes_are_fully_readonly(route_conn, mode):
    rows = [{"seq": i + 1, "op_type_name": "数铣"} for i in range(2000)]
    body = ({"mode": mode, "rows": rows} if mode == "rows" else
            {"mode": mode, "route_raw": "".join(str(row["seq"]) + row["op_type_name"] for row in rows)})
    before, changes = all_table_snapshot(route_conn), route_conn.total_changes
    with read_only_probe(route_conn) as statements:
        result = ProcessRoutePreviewService(route_conn).preview(body)
    assert result["can_confirm_route"] and len(result["operations"]) == 2000
    assert len(statements) == 4 and route_conn.total_changes == changes and not route_conn.in_transaction
    assert before == all_table_snapshot(route_conn)


def test_largest_sqlite_sequence_and_leading_zero_text_agree(route_conn):
    result = preview(route_conn, "0" * 100 + str(MAX_ROUTE_SEQUENCE) + "数铣")
    assert result["can_confirm_route"] and result["operations"][0]["sequence"] == MAX_ROUTE_SEQUENCE


def test_rows_text_budget_is_not_bypassed(route_conn):
    with pytest.raises(WorkbenchCommandRejected) as failure:
        ProcessRoutePreviewService(route_conn).preview({"mode": "rows", "rows": [{"seq": 1, "op_type_name": "a" * MAX_ROUTE_TEXT_BYTES}]})
    assert failure.value.status == 413


def test_unexpected_capability_query_error_propagates(route_conn):
    with patch.object(SupplierRepository, "list_capabilities", side_effect=TypeError("query implementation failure")):
        with pytest.raises(TypeError, match="query implementation failure"):
            preview(route_conn, "10数铣")


def test_invalid_persisted_supplier_label_cannot_break_public_dto(route_conn):
    route_conn.execute("UPDATE Suppliers SET name=? WHERE supplier_id='SUP-Z'", (sqlite3.Binary(b'bad-label'),))
    route_conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as failure:
        preview(route_conn, "10热处理")
    assert failure.value.status == 500 and failure.value.code == "storage_failure"
