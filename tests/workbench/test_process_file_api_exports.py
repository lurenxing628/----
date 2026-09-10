"""Exports use full selection and exactly the original snapshot and format."""

from io import BytesIO

import openpyxl
import pytest

from core.models.workbench_process_file import COLUMNS, INT64_MAX, LABELS
from core.services.workbench.process_file_codec import decode_process_file
from tests.workbench.process_file_api_support import BASE, file_api_fixture, node_contract
from tests.workbench.process_file_codec_support import source_cells
from tests.workbench.process_stage_api_support import rejected, success


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_template_is_header_only_and_read_only(file_api, kind, fmt):
    before = file_api.snapshot()
    response = file_api.client.get(BASE + "/process-files/" + kind + "/template", query_string={"format": fmt})
    assert response.status_code == 200, response.get_json()
    assert [list(row) for row in source_cells(response.data, fmt)] == [[LABELS[key] for key in COLUMNS[kind]]]
    assert decode_process_file(kind, response.data, fmt) == []
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment" in response.headers["Content-Disposition"]
    assert file_api.snapshot() == before


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
@pytest.mark.parametrize("selection", ["all", "filtered", "explicit"])
def test_export_complete_cross_page_selection(file_api, fmt, selection):
    scope = {"query": "PROC-00", "sort": [{"field": "business_code", "direction": "desc"}], "column_filters": {}}
    refs = [file_api.ref(code="PROC-004"), file_api.ref(code="PROC-002"), file_api.ref()] if selection == "explicit" else None
    before = file_api.snapshot()
    body, preview, response = file_api.export("route", scope=scope, fmt=fmt, selection=selection, refs=refs, size=1)
    node_contract("export", preview, "route", body=body)
    rows = decode_process_file("route", response.data, fmt)
    codes = [row["values"]["business_code"] for row in rows]
    expected = {"all": ["PROC-%_", "PROC-001", "PROC-002", "PROC-003", "PROC-004"],
                "filtered": ["PROC-004", "PROC-003", "PROC-002", "PROC-001"],
                "explicit": ["PROC-004", "PROC-002", "PROC-001"]}[selection]
    assert codes == expected
    assert preview["data"]["row_count"] == len(expected) > 1
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_detail_export_uses_detail_token(file_api, kind, fmt):
    target = file_api.ref()
    body, preview, response = file_api.export(kind, fmt=fmt, selection="explicit", refs=[target], target=target)
    node_contract("export", preview, kind, body=body)
    assert preview["data"]["scope"] == {} and preview["data"]["part_count"] == 1
    assert {row["values"]["business_code"] for row in decode_process_file(kind, response.data, fmt)} == {"PROC-001"}


@pytest.mark.parametrize("selection", ["filtered", "explicit"])
def test_empty_selection_exports_headers(file_api, selection):
    body, preview, response = file_api.export("route", selection=selection, scope={"query": "NO-MATCH"},
                                             refs=[] if selection == "explicit" else None)
    node_contract("export", preview, "route", body=body)
    assert preview["data"]["row_count"] == preview["data"]["part_count"] == 0
    assert decode_process_file("route", response.data, "csv") == []


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_exact_text_null_zero_int64_and_formula_export(file_api, fmt):
    code = "0000123"
    file_api.execute("INSERT INTO Parts(part_no,part_name,route_raw,remark) VALUES (?,?,?,?)",
                     (code, "=1+1", "  10\u8f66\u524a\r\n20\u68c0\u9a8c\rEND  ", "@SUM(A1:A2)"))
    file_api.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,setup_hours,unit_hours) VALUES (?,?,?,'internal',0,0)",
                     (code, INT64_MAX, "+formula\r\ntext"))
    target = file_api.ref(code=code)
    _, _, response = file_api.export("route", fmt=fmt, selection="explicit", refs=[target], target=target)
    assert decode_process_file("route", response.data, fmt)[0]["values"] == {
        "business_code": code, "label": "=1+1", "route_raw": "  10\u8f66\u524a\r\n20\u68c0\u9a8c\rEND  ", "remark": "@SUM(A1:A2)"}
    if fmt == "xlsx":
        wb = openpyxl.load_workbook(BytesIO(response.data), read_only=True, data_only=False)
        try:
            assert all(cell.data_type == "s" for row in wb.worksheets[0].iter_rows(min_row=2) for cell in row)
        finally:
            wb.close()
    _, _, hours = file_api.export("hours", fmt=fmt, selection="explicit", refs=[target], target=target)
    values = decode_process_file("hours", hours.data, fmt)[0]["values"]
    assert values["sequence"] == INT64_MAX and values["setup_hours"] == values["unit_hours"] == 0
    assert values["external_days"] is None and values["group_start"] is None


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_export_ten_thousand_rows_has_no_import_cap(file_api, kind, fmt):
    with file_api.database() as conn:
        if kind == "route":
            conn.executemany("INSERT INTO Parts(part_no,part_name) VALUES (?,?)",
                             [(f"SCALE-{n:05d}", "Scale") for n in range(10000)])
        else:
            conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('SCALE-HOURS','Scale')")
            conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_name,source,setup_hours,unit_hours) VALUES ('SCALE-HOURS',?,'Turning','internal',0,1)",
                             [(n,) for n in range(1, 10001)])
    body, preview, response = file_api.export(kind, fmt=fmt, selection="filtered", scope={"query": "SCALE-"}, size=1)
    node_contract("export", preview, kind, body=body)
    assert preview["data"]["row_count"] == 10000
    assert sum(1 for _ in source_cells(response.data, fmt)) == 10001


def test_snapshot_stale_on_unselected_full_fact_change(file_api):
    body, _ = file_api.export_body(selection="explicit", refs=[file_api.ref(code="PROC-002")])
    preview = success(file_api.file_post("route", "export-preview", body))
    file_api.execute("UPDATE Suppliers SET default_days=8 WHERE supplier_id='PROC-S'")
    before = file_api.snapshot()
    rejected(file_api.download("route", preview["data"]["export_ref"]), "snapshot_stale")
    rejected(file_api.file_post("route", "export-preview", body), "snapshot_stale")
    assert file_api.snapshot() == before


@pytest.mark.parametrize("value,fmt", [("x" * 32768, "xlsx"), ("bad\x00text", "csv"), ("bad\x0btext", "xlsx")],
                         ids=["xlsx-too-long", "csv-nul", "xlsx-control"])
def test_preflight_rejects_unencodable_text_before_issuing_download(file_api, value, fmt):
    file_api.execute("UPDATE Parts SET remark=? WHERE part_no='PROC-002'", (value,))
    body, _ = file_api.export_body(fmt=fmt, selection="explicit", refs=[file_api.ref(code="PROC-002")])
    before = file_api.snapshot()
    rejected(file_api.file_post("route", "export-preview", body), "invalid_input", 422)
    assert file_api.snapshot() == before


def test_preflight_rejects_unrepresentable_legacy_source_without_dropping_row(file_api):
    body, _ = file_api.export_body(selection="all")
    before = file_api.snapshot()
    rejected(file_api.file_post("hours", "export-preview", body), "invalid_input", 422)
    assert file_api.snapshot() == before
