"""Decoded route-file contracts, exact targets and read-only batched parsing."""

from copy import deepcopy

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import public_action_row
from core.services.process.workflow_state import read_workflow
from core.services.workbench.process_file_route import ProcessRouteFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_route_preview import ProcessRoutePreviewService
from tests.workbench.process_file_route_support import (
    PART,
    ROUTE,
    apply,
    decoded,
    fail_if_called,
    file_rows,
    operations,
    ref,
    review,
    route_file_database,
    snapshot,
    table,
)
from tests.workbench.process_route_support import read_only_probe

_fixture = route_file_database


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_real_codec_preview_is_read_only_and_public_contract_is_canonical(route_file_conn, fmt):
    conn = route_file_conn
    source = file_rows([{"business_code": PART, "label": " changed name ", "route_raw": ROUTE + "40新工种"},
                        {"business_code": "NEW", "label": "new", "route_raw": "10车削"}], fmt)
    original, before = deepcopy(source), snapshot(conn)
    with TransactionManager(conn).transaction():
        facts = WorkbenchProcessQueryService(conn).facts()
        original_facts = deepcopy(facts)
        with read_only_probe(conn):
            rows, extra = ProcessRouteFileOperations(conn).preview_rows(source, facts)
        assert facts == original_facts
    assert source == original and snapshot(conn) == before
    assert [row["result"] for row in rows] == ["update", "new"]
    assert extra == {"affected_groups": [], "zero_review_required": False}
    assert rows[0]["before"] == {"business_code": PART, "label": "轴套", "route_raw": ROUTE, "remark": "旧备注必须保留"}
    assert rows[0]["after"] == {**rows[0]["before"], "label": "changed name", "route_raw": ROUTE + "40新工种"}
    public = public_action_row(rows[0])
    assert not {"input", "expected", "related", "stage"} & public.keys()
    assert set(public["route_summary"]) == {"counts", "diagnostics", "can_confirm_route"}
    assert public["route_summary"]["counts"] == {"operations": 4, "recognized": 3, "unknown": 1}
    assert public["route_summary"]["can_confirm_route"]
    assert any(item["code"] == "unknown_op_type" for item in public["route_summary"]["diagnostics"])
    assert "route_file_private" not in repr(rows)
    assert "references" not in repr(rows) and "workflow" not in repr(rows)


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_omitted_and_blank_cells_keep_fields_and_explicit_null_only_clears_remark(route_file_conn, fmt):
    conn = route_file_conn
    before_ops = operations(conn)
    rows, _ = review(conn, file_rows([{"business_code": PART, "label": "", "remark": None}], fmt))
    assert rows[0]["changes"] == {"remark": {"before": "旧备注必须保留", "after": None}}
    assert rows[0]["route_summary"] is None
    results, affected = apply(conn, rows)
    assert results == [{"row": 2, "result": "committed", "entity_ref": ref(conn), "business_code": PART}]
    assert affected == [ref(conn)]
    assert conn.execute("SELECT part_name,remark,route_raw FROM Parts WHERE part_no=?", (PART,)).fetchone()[:] == ("轴套", None, ROUTE)
    assert operations(conn) == before_ops


@pytest.mark.parametrize("field,value", [("business_code", None), ("business_code", 0), ("label", None),
    ("label", 0), ("label", "  "), ("route_raw", None), ("route_raw", 0), ("route_raw", False), ("remark", 0), ("remark", "  ")])
def test_invalid_clears_and_nontext_are_rejected_without_defaulting(route_file_conn, field, value):
    before = snapshot(route_file_conn)
    rows, _ = review(route_file_conn, decoded({"business_code": PART, field: value}))
    assert rows[0]["result"] == "rejected" and rows[0]["errors"]
    with pytest.raises(WorkbenchCommandRejected):
        apply(route_file_conn, rows)
    assert snapshot(route_file_conn) == before


@pytest.mark.parametrize("raw,diagnostic", [("10车削10热处理", "duplicate_sequence"), ("10车削20", "missing_operation_name"),
    ("车削", "missing_sequence"), (" ", "empty_route"), ("0车削", "invalid_sequence"),
    ("10.5车削", "ambiguous_route_format")])
def test_invalid_routes_include_full_diagnostics_and_reject_whole_file(route_file_conn, raw, diagnostic):
    before = snapshot(route_file_conn)
    rows, _ = review(route_file_conn, decoded({"business_code": "GOOD", "label": "valid pending"},
                                             {"business_code": PART, "route_raw": raw}))
    assert rows[1]["result"] == "rejected" and not rows[1]["route_summary"]["can_confirm_route"]
    assert diagnostic in {item["code"] for item in rows[1]["route_summary"]["diagnostics"]}
    with pytest.raises(WorkbenchCommandRejected):
        apply(route_file_conn, rows)
    assert snapshot(route_file_conn) == before


@pytest.mark.parametrize("values", [{}, {"label": None}, {"label": 0}])
def test_new_part_requires_explicit_nonempty_name(route_file_conn, values):
    rows, _ = review(route_file_conn, decoded({"business_code": "NEW", **values}))
    assert rows[0]["result"] == "rejected"


@pytest.mark.parametrize("second", [PART, " " + PART + " "])
def test_all_duplicate_diagram_occurrences_rejected_after_normalization(route_file_conn, second):
    before = snapshot(route_file_conn)
    rows, _ = review(route_file_conn, decoded({"business_code": PART, "label": "first"}, {"business_code": second, "label": "last"}))
    assert all(row["result"] == "rejected" and any(error["code"] == "duplicate_entry" for error in row["errors"]) for row in rows)
    with pytest.raises(WorkbenchCommandRejected):
        apply(route_file_conn, rows)
    assert snapshot(route_file_conn) == before


def test_codec_errors_survive_and_block_valid_rows(route_file_conn):
    source = decoded({"business_code": "VALID", "label": "pending"}, {"business_code": PART, "label": "not allowed"})
    issue = {"row": 3, "field": "route_raw", "code": "invalid_input", "message": "bad original cell"}
    source[1]["errors"] = [issue]
    before = snapshot(route_file_conn)
    rows, _ = review(route_file_conn, source)
    assert rows[1]["errors"] == [issue] and rows[1]["result"] == "rejected"
    with pytest.raises(WorkbenchCommandRejected):
        apply(route_file_conn, rows)
    assert snapshot(route_file_conn) == before


@pytest.mark.parametrize("other", ["PROC-002", "NEW"])
def test_detail_target_is_strict_for_every_row_not_a_filter(route_file_conn, other):
    conn = route_file_conn
    before = snapshot(conn)
    rows, _ = review(conn, decoded({"business_code": PART, "remark": "change"}, {"business_code": other, "label": "other"}), ref(conn))
    assert rows[0]["result"] == "update" and rows[1]["result"] == "rejected"
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows)
    assert snapshot(conn) == before


@pytest.mark.parametrize("target", ["a" * 48, "bad-ref", 0, []])
def test_invalid_target_cannot_upsert_by_code(route_file_conn, target):
    rows, _ = review(route_file_conn, decoded({"business_code": PART, "remark": "change"}), target)
    assert rows[0]["result"] == "rejected"


def test_deleted_target_never_matches_a_recreated_same_number_part(route_file_conn):
    conn = route_file_conn
    old_ref = ref(conn, code="PROC-002")
    conn.execute("DELETE FROM Parts WHERE part_no='PROC-002'")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('PROC-002','replacement')")
    conn.commit()
    assert ref(conn, code="PROC-002") != old_ref
    before = snapshot(conn)
    rows, _ = review(conn, decoded({"business_code": "PROC-002", "label": "do not replace"}), old_ref)
    assert rows[0]["result"] == "rejected"
    with pytest.raises(WorkbenchCommandRejected):
        apply(conn, rows)
    assert snapshot(conn) == before


def test_padded_legacy_code_is_not_normalized_into_a_different_existing_part(route_file_conn):
    conn = route_file_conn
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES (' PROC-001 ','padded old record')")
    conn.commit()
    rows, _ = review(conn, decoded({"business_code": " PROC-001 ", "label": "wrong target"}))
    assert rows[0]["result"] == "rejected"


@pytest.mark.parametrize("raw", [ROUTE, "unparseable legacy route", "10车削20"])
def test_identical_route_is_never_reparsed_and_leaves_whole_database_untouched(route_file_conn, monkeypatch, raw):
    conn = route_file_conn
    conn.execute("UPDATE Parts SET route_raw=? WHERE part_no=?", (raw, PART))
    conn.commit()
    monkeypatch.setattr(ProcessRoutePreviewService, "preview", fail_if_called)
    monkeypatch.setattr(ProcessRoutePreviewService, "reference_snapshot", fail_if_called)
    monkeypatch.setattr("core.services.workbench.process_file_route.record_confirmation", fail_if_called)
    before = snapshot(conn)
    rows, extra = review(conn, decoded({"business_code": PART, "route_raw": raw}))
    assert rows[0]["route_summary"] is None and rows[0]["result"] == "unchanged"
    assert extra == {"affected_groups": [], "zero_review_required": False}
    results, affected = apply(conn, rows)
    assert results[0]["result"] == "unchanged" and affected == [ref(conn)]
    assert snapshot(conn) == before


def test_parse_reference_reads_are_constant_for_many_rows(route_file_conn):
    conn = route_file_conn
    traces = []
    with TransactionManager(conn).transaction():
        facts = WorkbenchProcessQueryService(conn).facts()
        for count in (1, 2000):
            with read_only_probe(conn) as statements:
                rows, _ = ProcessRouteFileOperations(conn).preview_rows(
                    decoded(*[{"business_code": "SCALE-" + str(index), "label": "scale", "route_raw": "10车削20热处理"}
                              for index in range(count)]), facts)
            assert all(row["result"] == "new" for row in rows)
            traces.append([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")])
    assert traces[0] == traces[1] and 0 < len(traces[0]) < 15


def test_snapshot_cache_does_not_survive_a_later_preview(route_file_conn):
    conn = route_file_conn
    source = decoded({"business_code": "NEW", "label": "new", "route_raw": "10notyetknown"})
    service = ProcessRouteFileOperations(conn)
    with TransactionManager(conn).transaction():
        first, _ = service.preview_rows(source, WorkbenchProcessQueryService(conn).facts())
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('LATER','notyetknown','internal')")
    conn.commit()
    with TransactionManager(conn).transaction():
        second, _ = service.preview_rows(source, WorkbenchProcessQueryService(conn).facts())
    assert first[0]["route_summary"]["counts"]["unknown"] == 1
    assert second[0]["route_summary"]["counts"]["recognized"] == 1


def test_both_interfaces_require_caller_transaction(route_file_conn):
    conn = route_file_conn
    service = ProcessRouteFileOperations(conn)
    facts = WorkbenchProcessQueryService(conn).facts()
    with pytest.raises(RuntimeError):
        service.preview_rows([], facts)
    with pytest.raises(RuntimeError):
        service.apply_rows([], discard_group_refs=[], confirm_zero_unit_hours=False)


def test_zero_review_flag_is_typed_but_never_confirms_hours(route_file_conn):
    conn = route_file_conn
    rows, extra = review(conn, decoded({"business_code": "ZERO", "label": "pending"}))
    before = snapshot(conn)
    with pytest.raises(ValidationError):
        apply(conn, rows, zero=1)
    assert snapshot(conn) == before
    result, refs = apply(conn, rows, zero=True)
    assert extra["zero_review_required"] is False and refs == [result[0]["entity_ref"]]
    assert read_workflow(conn, "ZERO")["route"]["state"] == "missing"
    assert table(conn, "WorkbenchProcessOperationConfirmations") == [dict(row) for row in conn.execute(
        "SELECT * FROM WorkbenchProcessOperationConfirmations WHERE part_ref<>? ORDER BY rowid", (refs[0],))]


def test_empty_decoded_file_is_an_atomic_noop(route_file_conn):
    conn = route_file_conn
    before = snapshot(conn)
    rows, extra = review(conn, [])
    assert rows == [] and extra == {"affected_groups": [], "zero_review_required": False}
    assert apply(conn, rows) == ([], []) and snapshot(conn) == before


@pytest.mark.parametrize("raw", [None, ""])
def test_explicitly_empty_new_route_stays_pending_without_parsing(route_file_conn, monkeypatch, raw):
    conn = route_file_conn
    monkeypatch.setattr(ProcessRoutePreviewService, "preview", fail_if_called)
    rows, _ = review(conn, decoded({"business_code": "PENDING", "label": "pending", "route_raw": raw}))
    assert rows[0]["result"] == "new" and rows[0]["after"]["route_raw"] is None
    apply(conn, rows)
    assert read_workflow(conn, "PENDING")["route"]["state"] == "missing"


def test_public_diagnostic_uses_exact_text_for_sqlite_sequence_beyond_javascript_precision(route_file_conn):
    conn = route_file_conn
    sequence = (1 << 63) - 1
    rows, _ = review(conn, decoded({"business_code": "BIG", "label": "big", "route_raw": str(sequence) + "unknown"}))
    assert rows[0]["route_summary"]["diagnostics"][0]["sequence"] == str(sequence)
    assert rows[0]["related"]["route"]["operations"][0]["sequence"] == sequence
    apply(conn, rows)
    assert list(operations(conn, "BIG")) == [sequence]


def test_valid_detail_target_updates_only_exact_part(route_file_conn):
    conn = route_file_conn
    target = ref(conn)
    rows, _ = review(conn, decoded({"business_code": PART, "remark": "detail update"}), target)
    assert rows[0]["entity_ref"] == target and rows[0]["result"] == "update"
    results, refs = apply(conn, rows)
    assert refs == [target] and results[0]["entity_ref"] == target
