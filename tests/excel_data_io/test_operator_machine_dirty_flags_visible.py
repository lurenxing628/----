"""回归测试：OperatorMachine 行存在旧格式/空白的 skill_level、is_primary 时，OperatorMachineQueryService.list_simple_rows 返回正确的 dirty_fields 与中文 dirty_reasons，且 /personnel/<id> 页面把"旧格式已自动修正"提示与受影响字段（技能等级/主操设备）对用户可见。"""

from __future__ import annotations

import pytest

from tests._support.legacy_http import canonical_resource
from tests._support.sqlite_snapshot import table_rows


def test_operator_machine_dirty_flags_visible(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection
    from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP200", "测试员乙", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC200", "设备乙", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC201", "设备丙", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP200", "MC200", "skilled", "off"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP200", "MC201", "", None),
        )
        conn.commit()
        before = table_rows(conn, "OperatorMachine")

        rows = OperatorMachineQueryService(conn).list_simple_rows()
    finally:
        conn.close()

    row_invalid = next((item for item in rows if item.get("operator_id") == "OP200" and item.get("machine_id") == "MC200"), None)
    assert row_invalid is not None, rows
    assert set(row_invalid.get("dirty_fields") or []) == {"skill_level", "is_primary"}, row_invalid
    assert str((row_invalid.get("dirty_reasons") or {}).get("skill_level") or "") != "", row_invalid
    assert str((row_invalid.get("dirty_reasons") or {}).get("is_primary") or "") != "", row_invalid

    row_blank = next((item for item in rows if item.get("operator_id") == "OP200" and item.get("machine_id") == "MC201"), None)
    assert row_blank is not None, rows
    assert set(row_blank.get("dirty_fields") or []) == {"skill_level", "is_primary"}, row_blank
    assert str((row_blank.get("dirty_reasons") or {}).get("skill_level") or "") != "", row_blank
    assert str((row_blank.get("dirty_reasons") or {}).get("is_primary") or "") != "", row_blank

    resp = app_client.get("/personnel/OP200")
    entity = canonical_resource(app_client, resp, "operator", "OP200")
    conn = get_connection(db_path)
    try:
        assert table_rows(conn, "OperatorMachine") == before
    finally:
        conn.close()
    warnings = [issue["message"] for issue in entity["issues"]
                if "技能等级" in issue["message"] and "主操设备" in issue["message"]]
    assert len(warnings) == 2, entity
    for machine_id in ("MC200", "MC201"):
        assert any(machine_id in message for message in warnings), warnings


@pytest.mark.parametrize(
    ("skill", "primary", "expected_fields"),
    [
        ("expert", "yes", ()),
        ("skilled", "off", ("skill_level", "is_primary")),
        ("", None, ("skill_level", "is_primary")),
        ("expert", "off", ("is_primary",)),
        ("invalid-level", "invalid-primary", ("skill_level", "is_primary")),
    ],
    ids=("canonical", "legacy", "blank", "primary-only", "invalid"),
)
def test_workbench_authorization_issues_are_read_only(app_client, db_path, skill, primary, expected_fields):
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    tables = ("Operators", "Machines", "OperatorMachine", "OperatorSkill", "WorkbenchOperatorProfiles", "WorkbenchEntityRefs")
    try:
        conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES('OP-PAIR','paired operator','active')")
        conn.execute("INSERT INTO Machines(machine_id,name,status) VALUES('MC-PAIR','paired machine','active')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id,skill_level,is_primary) VALUES('OP-PAIR','MC-PAIR',?,?)",
                     (skill, primary))
        conn.commit()
        before = {table: table_rows(conn, table) for table in tables}
    finally:
        conn.close()
    entity = canonical_resource(app_client, app_client.get("/personnel/OP-PAIR"), "operator", "OP-PAIR")
    assert entity["relationships"]["machine_authorization_count"] == 1
    assert entity["relationships"]["skill_refs"] == [] and entity["relationships"]["skills_declared"] is False
    issues = [issue for issue in entity["issues"] if issue["code"] == "machine_authorization_dirty"]
    assert len(issues) == (1 if expected_fields else 0)
    if issues:
        assert set(issues[0]["fields"]) == set(expected_fields)
        message = issues[0]["message"]
        assert "MC-PAIR" in message and "原值没有被改" in message
        for field, label in (("skill_level", "技能等级"), ("is_primary", "主操设备")):
            assert (label in message) is (field in expected_fields)
        assert all(value not in message for value in (skill, primary) if value)
    conn = get_connection(db_path)
    try:
        assert {table: table_rows(conn, table) for table in tables} == before
    finally:
        conn.close()
