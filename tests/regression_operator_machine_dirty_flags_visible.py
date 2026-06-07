"""回归测试：OperatorMachine 行存在旧格式/空白的 skill_level、is_primary 时，OperatorMachineQueryService.list_simple_rows 返回正确的 dirty_fields 与中文 dirty_reasons，且 /personnel/<id> 页面把"旧格式已自动修正"提示与受影响字段（技能等级/主操设备）对用户可见。"""

from __future__ import annotations


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


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
    _assert_status(resp, "GET /personnel/OP200")
    html = resp.data.decode("utf-8", errors="ignore")

    assert "以下 2 条记录中有部分字段的旧格式已被系统自动修正" in html, html
    assert "涉及字段：" in html, html
    assert "技能等级" in html, html
    assert "主操设备" in html, html
