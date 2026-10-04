"""可操作设备关系文件的导入合同：增量更新、不删除、主操连带在预检就算准。"""

from uuid import uuid4

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.relation_files.files import WorkbenchRelationFileService
from tests.workbench.relation_file_support import (  # noqa: F401
    file_bytes,
    links_of,
    relation_database,
    resource_database,
)

KIND = "operator_machine"
HEADERS = ("工号", "设备编号", "技能等级", "主操设备")


def preview(conn, rows, fmt="csv", headers=HEADERS):
    return WorkbenchRelationFileService(conn, KIND).preview_import(
        file_bytes(rows, fmt, headers), file_format=fmt)


def confirm(conn, document, fmt="csv", rows=None, headers=HEADERS):
    content = file_bytes(rows, fmt, headers)
    action = document.as_dict()["operation"]
    return WorkbenchCommandService(conn).execute(
        request_key="relation-file-" + uuid4().hex, action=action, context_ref=document.digest,
        normalized_input={"preview_ref": document.digest}, guard=lambda: None,
        mutate=lambda _: WorkbenchRelationFileService(conn, KIND).confirm_import(
            document, content, file_format=fmt))


def results(document):
    return [(row["row"], row["result"]) for row in document.as_dict()["rows"]]


def test_new_links_are_created_and_absent_links_stay(relation_env):
    conn = relation_env
    rows = [("RO1", "RM1", "熟练", "是")]
    document = preview(conn, rows)
    assert results(document) == [(2, "new")]
    assert confirm(conn, document, rows=rows)["result"] == "committed"
    assert links_of(conn, "RO1") == {"RM1": ("expert", "yes")}
    # RO2 从未出现在文件里，完全不受影响
    assert links_of(conn, "RO2") == {}


def test_skill_change_is_update_and_blank_keeps_current(relation_env):
    conn = relation_env
    first = [("RO1", "RM1", "普通", "否")]
    confirm(conn, preview(conn, first), rows=first)
    changed = [("RO1", "RM1", "熟练", "")]
    document = preview(conn, changed)
    body = document.as_dict()["rows"][0]
    assert body["result"] == "update" and body["changes"]["skill_level"]["after"] == "expert"
    assert "is_primary" not in body["changes"]
    confirm(conn, document, rows=changed)
    assert links_of(conn, "RO1") == {"RM1": ("expert", "no")}


def test_unchanged_row_is_not_written(relation_env):
    conn = relation_env
    rows = [("RO1", "RM1", "普通", "否")]
    confirm(conn, preview(conn, rows), rows=rows)
    document = preview(conn, rows)
    assert results(document) == [(2, "unchanged")]
    assert confirm(conn, document, rows=rows)["result"] == "unchanged"


def test_primary_handover_is_resolved_before_writing(relation_env):
    """把主操给新设备时，旧主操那一行在预检就标成更新，确认后结果与预检一致。"""
    conn = relation_env
    seed = [("RO1", "RM1", "普通", "是"), ("RO1", "RM2", "普通", "否")]
    confirm(conn, preview(conn, seed), rows=seed)
    assert links_of(conn, "RO1") == {"RM1": ("normal", "yes"), "RM2": ("normal", "no")}
    handover = [("RO1", "RM1", "", ""), ("RO1", "RM2", "", "是")]
    document = preview(conn, handover)
    rows = document.as_dict()["rows"]
    assert [row["result"] for row in rows] == ["update", "update"]
    assert rows[0]["changes"]["is_primary"] == {"before": "yes", "after": "no"}
    assert rows[1]["changes"]["is_primary"] == {"before": "no", "after": "yes"}
    assert any("RM1" in note for note in rows[1]["notes"])
    assert rows[0]["notes"] and rows[0]["requires_confirmation"]
    confirm(conn, document, rows=handover)
    assert links_of(conn, "RO1") == {"RM1": ("normal", "no"), "RM2": ("normal", "yes")}


def test_primary_handover_when_old_primary_absent_from_file(relation_env):
    """旧主操没写进文件时，新主操那一行必须讲明它会被取消。"""
    conn = relation_env
    seed = [("RO1", "RM1", "普通", "是")]
    confirm(conn, preview(conn, seed), rows=seed)
    handover = [("RO1", "RM2", "普通", "是")]
    document = preview(conn, handover)
    row = document.as_dict()["rows"][0]
    assert row["result"] == "new" and row["requires_confirmation"]
    assert any("RM1" in note for note in row["notes"])
    confirm(conn, document, rows=handover)
    assert links_of(conn, "RO1") == {"RM1": ("normal", "no"), "RM2": ("normal", "yes")}


def test_explicit_no_on_current_primary_leaves_person_without_primary(relation_env):
    conn = relation_env
    seed = [("RO1", "RM1", "普通", "是")]
    confirm(conn, preview(conn, seed), rows=seed)
    drop = [("RO1", "RM1", "普通", "否")]
    document = preview(conn, drop)
    assert document.as_dict()["rows"][0]["changes"]["is_primary"] == {"before": "yes", "after": "no"}
    confirm(conn, document, rows=drop)
    assert links_of(conn, "RO1") == {"RM1": ("normal", "no")}


def test_two_primary_rows_for_one_operator_are_rejected(relation_env):
    conn = relation_env
    document = preview(conn, [("RO1", "RM1", "", "是"), ("RO1", "RM2", "", "是")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert all("最多只能有一台主操" in row["errors"][0]["message"] for row in document.as_dict()["rows"])


def test_duplicate_pair_rows_are_rejected(relation_env):
    conn = relation_env
    document = preview(conn, [("RO1", "RM1", "普通", "否"), ("RO1", "RM1", "熟练", "否")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["code"] == "duplicate_entry"


@pytest.mark.parametrize("row", (("NOPE", "RM1", "", ""), ("RO1", "NOPE", "", ""), ("", "RM1", "", ""),
                                 (" RO1", "RM1", "", ""), ("RO1", "RM1", "很熟", ""), ("RO1", "RM1", "", "也许")))
def test_bad_rows_are_rejected_without_writing(relation_env, row):
    conn = relation_env
    before = links_of(conn, "RO1")
    document = preview(conn, [row])
    assert results(document) == [(2, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(conn, document, rows=[row])
    assert links_of(conn, "RO1") == before


def test_one_bad_row_blocks_the_whole_batch(relation_env):
    conn = relation_env
    rows = [("RO1", "RM1", "普通", "否"), ("RO1", "NOPE", "普通", "否")]
    document = preview(conn, rows)
    assert results(document) == [(2, "new"), (3, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(conn, document, rows=rows)
    assert links_of(conn, "RO1") == {}


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_round_trip_export_then_import_reports_no_change(relation_env, fmt):
    conn = relation_env
    seed = [("RO1", "RM1", "熟练", "是"), ("RO2", "RM2", "初级", "否")]
    confirm(conn, preview(conn, seed), rows=seed)
    with TransactionManager(conn).transaction():
        download = WorkbenchRelationFileService(conn, KIND).export(fmt, scope={})
    # 导出全部人员时还会带上种子里 O1 的那条关联，回导后同样应当判为未改动。
    assert download.row_count == 3
    document = WorkbenchRelationFileService(conn, KIND).preview_import(download.content, file_format=fmt)
    assert [row["result"] for row in document.as_dict()["rows"]] == ["unchanged"] * 3


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_has_headers_and_no_rows(relation_env, fmt):
    download = WorkbenchRelationFileService.template(KIND, fmt)
    assert download.row_count == 0 and "可操作设备导入模板." + fmt == download.filename


def test_unknown_headers_are_rejected(relation_env):
    conn = relation_env
    with pytest.raises(ValidationError):
        preview(conn, [("RO1", "RM1")], headers=("工号", "随便什么"))
    with pytest.raises(ValidationError):
        preview(conn, [("RO1",)], headers=("工号",))


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_writes_the_same_words_the_dropdown_offers(relation_env, fmt):
    """导出的值必须和文件里的下拉、填写说明用同一套词。

    原来库里存的英文代号被直接写进格子：下拉给的是「普通」，格子里却是 normal，
    用户点一下下拉就改了值，想照原样填回 normal 又会被 Excel 的数据校验拒掉。
    """
    from tests.workbench.relation_file_support import decode

    conn = relation_env
    seed = [("RO1", "RM1", "熟练", "是"), ("RO2", "RM2", "初级", "否")]
    confirm(conn, preview(conn, seed), rows=seed)
    with TransactionManager(conn).transaction():
        download = WorkbenchRelationFileService(conn, KIND).export(fmt, scope={})

    headers, rows = decode(download, fmt)
    level_at, primary_at = headers.index("技能等级"), headers.index("主操设备")
    levels = {row[level_at] for row in rows}
    primaries = {row[primary_at] for row in rows}
    assert levels <= {"初级", "普通", "熟练"}, f"技能等级导出了下拉里没有的词：{levels}"
    assert primaries <= {"是", "否"}, f"主操设备导出了下拉里没有的词：{primaries}"
    assert ("RO1", "RM1", "熟练", "是") in {(r[0], r[1], r[level_at], r[primary_at]) for r in rows}


def _legacy_two_primaries(conn):
    # 规则收紧前留下的旧数据：同一个人两台设备都标成主操。
    for machine in ("RM1", "RM2"):
        conn.execute("INSERT INTO OperatorMachine(operator_id, machine_id, skill_level, is_primary) VALUES ('RO1', ?, 'expert', 'yes')",
                     (machine,))
    conn.commit()


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_legacy_two_primaries_round_trip_is_unchanged_and_never_rewritten(relation_env, fmt):
    conn = relation_env
    _legacy_two_primaries(conn)
    with TransactionManager(conn).transaction():
        download = WorkbenchRelationFileService(conn, KIND).export(fmt, scope={})
    document = WorkbenchRelationFileService(conn, KIND).preview_import(download.content, file_format=fmt)
    body = document.as_dict()
    assert [row["result"] for row in body["rows"]] == ["unchanged"] * download.row_count
    assert not any(row["notes"] or row.get("requires_confirmation") for row in body["rows"])
    outcome = WorkbenchCommandService(conn).execute(
        request_key="relation-file-" + uuid4().hex, action=body["operation"], context_ref=document.digest,
        normalized_input={"preview_ref": document.digest}, guard=lambda: None,
        mutate=lambda _: WorkbenchRelationFileService(conn, KIND).confirm_import(document, download.content, file_format=fmt))
    assert outcome["result"] == "unchanged"
    assert links_of(conn, "RO1") == {"RM1": ("expert", "yes"), "RM2": ("expert", "yes")}


def test_legacy_two_primaries_still_block_any_real_change_to_that_person(relation_env):
    conn = relation_env
    _legacy_two_primaries(conn)
    # 有一行真要改（技能等级），确认时会写主操，就仍按一人一台主操的规则拒绝，不替用户挑一台。
    document = preview(conn, [("RO1", "RM1", "熟练", "是"), ("RO1", "RM2", "普通", "是")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert all("最多只能有一台主操" in row["errors"][0]["message"] for row in document.as_dict()["rows"])


def test_new_second_primary_is_still_rejected_when_first_is_unchanged(relation_env):
    conn = relation_env
    seed = [("RO1", "RM1", "熟练", "是"), ("RO1", "RM2", "熟练", "否")]
    confirm(conn, preview(conn, seed), rows=seed)
    document = preview(conn, [("RO1", "RM1", "熟练", "是"), ("RO1", "RM2", "熟练", "是")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert links_of(conn, "RO1") == {"RM1": ("expert", "yes"), "RM2": ("expert", "no")}
