"""Real file/service journeys preserve operation identity and unfinished work."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_process_file import table_descriptor
from core.services.process.workflow_state import read_workflow
from core.services.workbench.process.file_codec import decode_process_file, encode_process_file
from core.services.workbench.process.file_export import process_export_rows
from core.services.workbench.process.files import WorkbenchProcessFileService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from core.services.workbench.process.route_preview import ProcessRoutePreviewService
from tests.workbench.process_commands_support import identity_for, run_stage, stage_database
from tests.workbench.process_file_codec_support import file_bytes
from tests.workbench.process_file_hours_support import hours_database

_fixtures = (stage_database, hours_database)


def _export(conn, kind, code):
    facts = WorkbenchProcessQueryService(conn).facts()
    part = next(row for row in facts["parts"] if row["part_no"] == code)
    return list(process_export_rows(kind, [part], facts))


def _import(conn, kind, rows, fmt):
    content = encode_process_file(kind, rows, fmt).content
    service = WorkbenchProcessFileService(conn)
    preview, extra = service.preview_import(kind, content, file_format=fmt)
    assert preview.as_dict()["summary"]["rejected"] == 0
    with TransactionManager(conn).transaction(begin_immediate=True):
        outcome = service.confirm_import(preview, content, discard_group_refs=[],
                                         confirm_zero_unit_hours=extra["zero_review_required"])
    return preview.as_dict(), outcome


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("name", ("3D打印", "Heat treatment", "Paint; coat", '检验"尺寸"', "表面\n处理"))
def test_structured_route_export_edit_reimport_keeps_original_operation(stage_conn, fmt, name):
    conn = stage_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('READABLE',?,'internal')", (name,))
    conn.commit()
    run_stage(conn, "route_confirm", {"route": {"mode": "rows", "rows": [{"seq": 10, "op_type_name": name}]}},
              identity=identity_for(conn, "PROC-002"))
    before = dict(conn.execute("SELECT * FROM PartOperations WHERE part_no='PROC-002'").fetchone())
    rows = _export(conn, "route", "PROC-002")
    unchanged, outcome = _import(conn, "route", rows, fmt)
    assert outcome.result == "unchanged"
    assert dict(conn.execute("SELECT * FROM PartOperations WHERE part_no='PROC-002'").fetchone()) == before
    # A planner adds one operation in the same route cell, keeping one part per row.
    rows[0]["route_raw"] += "；20: 检验"
    preview, outcome = _import(conn, "route", rows, fmt)
    assert outcome.result == "committed"
    operations = list(conn.execute("SELECT id,seq,op_type_name,status FROM PartOperations WHERE part_no='PROC-002' ORDER BY seq"))
    assert [(r["seq"], r["op_type_name"], r["status"]) for r in operations] == [(10, name, "active"), (20, "检验", "active")]
    assert operations[0]["id"] == before["id"]
    summary = preview["rows"][0]["route_summary"]
    assert [(r["sequence"], r["change"]) for r in summary["differences"]] == [(10, "retained"), (20, "added")]
    assert summary["operations"][0]["op_type_name"] == name


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_exported_missing_hours_allow_partial_save_without_confirming_readiness(hours_conn, fmt):
    conn = hours_conn
    conn.execute("UPDATE PartOperations SET unit_hours=NULL WHERE part_no='P1' AND seq=2")
    conn.commit()
    rows = _export(conn, "hours", "P1")
    assert "unit_hours" not in next(row for row in rows if row["sequence"] == 2)
    next(row for row in rows if row["sequence"] == 1)["unit_hours"] = 1.5
    _, outcome = _import(conn, "hours", rows, fmt)
    assert outcome.result == "committed"
    assert conn.execute("SELECT unit_hours FROM PartOperations WHERE part_no='P1' AND seq=1").fetchone()[0] == 1.5
    assert conn.execute("SELECT unit_hours FROM PartOperations WHERE part_no='P1' AND seq=2").fetchone()[0] is None
    assert not read_workflow(conn, "P1")["ready"]
    assert read_workflow(conn, "P1")["hours"]["state"] == "unconfirmed"


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_merged_cycle_is_edited_once_and_conflicting_multiple_values_still_fail(hours_conn, fmt):
    rows = _export(hours_conn, "hours", "P1")
    totals = [row for row in rows if "group_total_days" in row]
    assert [row["sequence"] for row in totals] == [3]
    totals[0]["group_total_days"] = 9.25
    _, outcome = _import(hours_conn, "hours", rows, fmt)
    assert outcome.result == "committed"
    assert hours_conn.execute("SELECT total_days FROM ExternalGroups WHERE group_id='P1-G'").fetchone()[0] == 9.25
    next(row for row in rows if row["sequence"] == 5)["group_total_days"] = 8.25
    content = encode_process_file("hours", rows, fmt).content
    preview, _ = WorkbenchProcessFileService(hours_conn).preview_import("hours", content, file_format=fmt)
    assert preview.as_dict()["summary"]["rejected"] == 2
    assert any(error["code"] == "group_value_conflict" for row in preview.as_dict()["rows"] for error in row["errors"])


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_blank_lines_skip_but_content_without_part_number_is_reported_at_source_row(fmt):
    content = file_bytes(["图号", "名称"], [["P1", "甲"], [None, None], [None, "有内容"]], fmt)
    rows, _ = decode_process_file("route", content, fmt)
    assert [row["row"] for row in rows] == [2, 4]
    assert rows[1]["errors"][0]["field"] == "business_code"


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_examples_are_parseable_and_old_route_header_remains_supported(stage_conn, fmt):
    descriptor = table_descriptor("route")
    content = file_bytes([column["label"] for column in descriptor["columns"]], descriptor["sample_rows"], fmt)
    rows, _ = decode_process_file("route", content, fmt)
    for row in rows:
        assert not row["errors"]
        parsed = ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": row["values"]["route_raw"]})
        assert parsed["can_confirm_route"]
    old = file_bytes(["图号", "工艺路线字符串"], [["P1", "10车削20检验"]], fmt)
    assert decode_process_file("route", old, fmt)[0][0]["values"]["route_raw"] == "10车削20检验"
