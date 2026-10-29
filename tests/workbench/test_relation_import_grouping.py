"""No-op relationship files keep historical primaries with linear row inspections."""

import pytest

from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.relation_files import files as module
from core.services.workbench.resource.relation_files.file_codec import read_relation_file
from core.services.workbench.resource.relation_files.file_writer import write_relation_file
from tests.workbench.calendar_file_support import file_bytes
from tests.workbench.resource_entity_support import identity_for, resource_database  # noqa: F401


def test_primary_planning_groups_rows_once_and_preserves_unchanged_legacy_groups(monkeypatch):
    count = 300
    rows = [{"errors": [], "values": {"operator_code": f"O{i}", "machine_code": "M1",
             "skill_level": "normal", "is_primary": "no"}} for i in range(count)]
    current = {f"O{i}": {"M1": {"skill_level": "normal", "is_primary": "no"}} for i in range(count)}
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M1", "is_primary": "yes"}})
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M2", "is_primary": "yes"}})
    current["legacy"] = {code: {"skill_level": "normal", "is_primary": "yes"} for code in ("M1", "M2")}
    inspections, original = [], module._blocked

    def captured(row):
        inspections.append(True)
        return original(row)

    monkeypatch.setattr(module, "_blocked", captured)
    result = object.__new__(module.WorkbenchRelationFileService)._final_primaries(rows, current)
    assert all(not result[f"O{i}"] for i in range(count))
    assert result["legacy"] == {"M1", "M2"} and all(not row["errors"] for row in rows)
    assert len(inspections) <= 4 * len(rows)


def _replaced_primaries(current, primaries):
    return {operator: [code for code, link in sorted(links.items())
                       if link["is_primary"] == "yes" and code not in primaries[operator]]
            for operator, links in current.items()}


def test_primary_notes_cover_unchanged_claim_demoting_legacy_primary_without_false_positive_on_blank():
    service = object.__new__(module.WorkbenchRelationFileService)
    current = {
        "O1": {
            "M1": {"skill_level": "normal", "is_primary": "yes"},
            "M2": {"skill_level": "normal", "is_primary": "yes"},
            "M3": {"skill_level": "normal", "is_primary": "no"},
        }
    }
    claim_rows = [
        {"row": 1, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M1", "skill_level": "normal", "is_primary": "yes"}},
        {"row": 2, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M3", "skill_level": "expert", "is_primary": None}},
    ]
    primaries = service._final_primaries(claim_rows, current)
    assert primaries["O1"] == {"M1"}
    replaced = _replaced_primaries(current, primaries)
    for row in claim_rows:
        service._classify(row, current, primaries, replaced)
    assert claim_rows[0]["result"] == "unchanged"
    assert claim_rows[0]["notes"] == ["确认后 M2 不再是这个人的主操设备。"]
    assert claim_rows[0]["requires_confirmation"] is True

    drop_rows = [
        {"row": 1, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M1", "skill_level": "expert", "is_primary": None}},
        {"row": 2, "errors": [], "notes": [], "requires_confirmation": False,
         "values": {"operator_code": "O1", "machine_code": "M2", "skill_level": None, "is_primary": "no"}},
    ]
    primaries = service._final_primaries(drop_rows, current)
    assert primaries["O1"] == {"M1"}
    replaced = _replaced_primaries(current, primaries)
    for row in drop_rows:
        service._classify(row, current, primaries, replaced)
    assert drop_rows[0]["result"] == "update"
    assert drop_rows[0]["notes"] == []
    assert drop_rows[0]["requires_confirmation"] is False


def test_relation_export_in_read_snapshot_reuses_loaded_table_facts(resource_conn, monkeypatch):
    conn = resource_conn
    reader = WorkbenchResourceQueryService(conn, "operator")
    service = module.WorkbenchRelationFileService(conn, "operator_machine", reader=reader)
    operator = identity_for(conn, "operator")
    assert operator is not None

    def unexpected(*args, **kwargs):
        raise AssertionError("export inside read_snapshot must reuse table_facts instead of querying repo/links")

    monkeypatch.setattr(service.links, "list_simple_rows_for_operators", unexpected)
    monkeypatch.setattr(service.repo, "raw_many", unexpected)
    with reader.read_snapshot():
        args, count = service.preview_export("selected", scope={}, selected_refs=[operator.ref])
        rows = service.export_rows("csv", **args)
    assert count == 1 and len(rows) == 1
    assert rows[0]["operator_code"] == "O1" and rows[0]["machine_code"] == "M1"


def test_relation_confirm_import_rejects_same_second_recreated_operator_or_machine(resource_conn, monkeypatch):
    import openpyxl.xml

    conn = resource_conn
    service = module.WorkbenchRelationFileService(conn, "operator_machine")
    content = file_bytes(
        [("EMPTY", "M1", "普通", "否")],
        headers=("工号", "设备编号", "技能等级", "主操设备"),
    )
    preview = service.preview_import(content, file_format="csv")
    assert preview.as_dict()["summary"]["rejected"] == 0

    monkeypatch.setattr(openpyxl.xml, "LXML", False)
    download = write_relation_file(
        "operator_machine",
        [{
            "operator_code": "O1",
            "operator_label": "张\r\n三",
            "machine_code": "M1",
            "machine_label": "设\r\n备",
            "skill_level": "掌握",
            "is_primary": "是",
        }],
        "xlsx",
    )
    parsed_rows, _ = read_relation_file("operator_machine", download.content, "xlsx")
    assert parsed_rows[0]["values"]["operator_label"] == "张\r\n三"
    assert parsed_rows[0]["values"]["machine_label"] == "设\r\n备"


def test_relation_import_rejects_null_marker_on_required_columns(resource_conn):
    service = module.WorkbenchRelationFileService(resource_conn, "operator_machine")
    content = file_bytes([("O1", "M1", r"\N", r"\N")], headers=("工号", "设备编号", "技能等级", "主操设备"))
    preview = service.preview_import(content, file_format="csv").as_dict()
    assert preview["summary"]["rejected"] == 1
    row = preview["rows"][0]
    assert row["result"] == "rejected"
    assert [error["field"] for error in row["errors"]] == ["skill_level", "is_primary"]
