"""Chinese choices and ordinary code lists remain compatible with old files."""

import pytest

from core.models.workbench_resource_file import ENUM_LABELS, file_columns
from core.services.workbench.facts.file_codec import read_resource_file
from core.services.workbench.facts.file_lists import decode_code_list, encode_code_list
from core.services.workbench.facts.file_writer import write_resource_file
from core.services.workbench.resource.files import WorkbenchResourceFileService
from tests.workbench.resource_file_support import confirm, decode, exported, file_bytes, resource_database

_fixture = resource_database


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("field,kind", (("category", "op_type"), ("default_merge_mode", "op_type"), ("status", "machine")))
def test_chinese_choices_decode_to_the_same_values_as_old_codes(fmt, field, kind):
    for code, label in ENUM_LABELS[field].items():
        for value in (code, label):
            rows, _ = read_resource_file(kind, file_bytes([["TEST", value]], fmt, ("编号", field)), fmt)
            assert not rows[0]["errors"]
            assert rows[0]["values"][field] == code


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("value", ("OT1、OT2", "OT1, OT2", "OT1；OT2", "OT1\nOT2", '["OT1","OT2"]'))
def test_readable_and_old_skill_lists_work_through_real_preview_and_confirmation(resource_conn, fmt, value):
    content = file_bytes([["O1", "可用", value]], fmt, ("编号", "状态", "技能工种编号"))
    service = WorkbenchResourceFileService(resource_conn, "operator")
    preview = service.preview_import(content, file_format=fmt, scope={})
    assert preview.as_dict()["summary"]["rejected"] == 0
    confirm(resource_conn, "operator", preview, content, fmt)
    assert [row[0] for row in resource_conn.execute("SELECT op_type_id FROM OperatorSkill WHERE operator_id='O1' ORDER BY op_type_id")] == ["OT1", "OT2"]


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_blank_keeps_skills_but_chinese_clear_explicitly_removes_them(resource_conn, fmt):
    service = WorkbenchResourceFileService(resource_conn, "operator")
    for value, clear in (("", False), ("清除", True)):
        content = file_bytes([["O1", value]], fmt, ("编号", "技能工种编号数组"))
        preview = service.preview_import(content, file_format=fmt, scope={})
        assert preview.as_dict()["summary"]["rejected"] == 0
        confirm(resource_conn, "operator", preview, content, fmt)
        count = resource_conn.execute("SELECT COUNT(*) FROM OperatorSkill WHERE operator_id='O1'").fetchone()[0]
        assert (count == 0) is clear


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("value", ("OT1,,OT2", "OT1、OT1", '"OT1', 'OT1"、OT2', '"OT1"OT2', "OT1；"))
def test_ambiguous_or_repeated_lists_remain_rejected(fmt, value):
    rows, _ = read_resource_file("operator", file_bytes([["O1", value]], fmt, ("编号", "技能工种编号")), fmt)
    assert rows[0]["errors"][0]["field"] == "skill_codes"


@pytest.mark.parametrize("values", (["OT1", "OT2"], ["清除"], ["[legacy]"], ["A,B", "C；D"], ['A"B', "line\r\ncode"], []))
def test_exported_code_lists_are_reversible_even_for_reserved_or_delimited_codes(values):
    assert decode_code_list(encode_code_list(values), "skill_codes") == values


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_readable_list_file_roundtrip_preserves_quoted_separators_and_carriage_returns(fmt):
    values = ["OT1", "line\r\ncode", "A,B", "清除", "[old]", 'A"B']
    row = {field: None for field in file_columns("operator")}
    row.update(business_code="O1", label="operator", status="active", skill_codes=values)
    content = write_resource_file("operator", [row], fmt).content
    parsed = read_resource_file("operator", content, fmt)[0][0]
    assert not parsed["errors"]
    assert parsed["values"]["skill_codes"] == values


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_chinese_status_does_not_bypass_resource_kind_validation(resource_conn, fmt):
    content = file_bytes([["M1", "请假"]], fmt, ("编号", "状态"))
    preview = WorkbenchResourceFileService(resource_conn, "machine").preview_import(content, file_format=fmt, scope={})
    assert preview.as_dict()["summary"]["rejected"] == 1


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_shows_chinese_status_and_plain_code_lists(resource_conn, fmt):
    result = exported(resource_conn, "operator", fmt)
    headers, rows = decode(result, fmt)
    data = {row[headers.index("编号")]: dict(zip(headers, row)) for row in rows}
    assert data["O1"]["状态"] == "可用"
    assert data["O1"]["技能工种编号"] == "OT1"
    preview = WorkbenchResourceFileService(resource_conn, "operator").preview_import(result.content, file_format=fmt, scope={})
    assert preview.as_dict()["summary"]["rejected"] == 0
    assert confirm(resource_conn, "operator", preview, result.content, fmt)["result"] == "unchanged"
