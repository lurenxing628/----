"""回归测试：设备详情页 /equipment/<id> 与人员详情页 /personnel/<id> 的读侧归一——把库里 legacy 的 OperatorMachine.skill_level("skilled") 显示为 expert 选中、is_primary 的中文"是"/"off" 归一为勾选/未勾选；link/update 写回后落库为规范值 expert 与 yes/no。"""

from __future__ import annotations

import re
from typing import Optional, Tuple


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _selected_skill_value(html: str) -> Optional[str]:
    m = re.search(r'<option value="(beginner|normal|expert)"\s+selected>', html)
    return m.group(1) if m else None


def _is_primary_checked(html: str, form_id: str) -> bool:
    pattern = rf'name="is_primary" value="yes" form="{re.escape(form_id)}"\s+checked'
    return re.search(pattern, html) is not None


def _fetch_link(conn, operator_id: str, machine_id: str) -> Tuple[Optional[str], Optional[str]]:
    row = conn.execute(
        "SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
        (operator_id, machine_id),
    ).fetchone()
    if row is None:
        raise AssertionError(f"未找到关联：{operator_id}/{machine_id}")
    return row["skill_level"], row["is_primary"]


def test_operator_machine_detail_readside_normalization(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP200", "测试员乙"))
        conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC100", "设备甲"))
        conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC200", "设备乙"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP100", "MC100", "skilled", "是"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP200", "MC200", "skilled", "off"),
        )
        conn.commit()
    finally:
        conn.close()

    resp_equipment = app_client.get("/equipment/MC100")
    _assert_status(resp_equipment, "GET /equipment/MC100")
    html_equipment = resp_equipment.data.decode("utf-8", errors="ignore")
    assert _selected_skill_value(html_equipment) == "expert", "设备详情页未将 skilled 归一显示为 expert"
    assert _is_primary_checked(html_equipment, "linkform_0"), "设备详情页未将中文“是”归一显示为勾选"

    resp_personnel = app_client.get("/personnel/OP200")
    _assert_status(resp_personnel, "GET /personnel/OP200")
    html_personnel = resp_personnel.data.decode("utf-8", errors="ignore")
    assert _selected_skill_value(html_personnel) == "expert", "人员详情页未将 skilled 归一显示为 expert"
    assert not _is_primary_checked(html_personnel, "linkform_0"), "人员详情页未将 off 归一显示为未勾选"

    resp_save_equipment = app_client.post(
        "/equipment/MC100/link/update",
        data={"operator_id": "OP100", "skill_level": "expert", "is_primary": "yes"},
        follow_redirects=True,
    )
    _assert_status(resp_save_equipment, "POST /equipment/MC100/link/update")

    resp_save_personnel = app_client.post(
        "/personnel/OP200/link/update",
        data={"machine_id": "MC200", "skill_level": "expert"},
        follow_redirects=True,
    )
    _assert_status(resp_save_personnel, "POST /personnel/OP200/link/update")

    conn = get_connection(db_path)
    try:
        skill1, primary1 = _fetch_link(conn, "OP100", "MC100")
        assert skill1 == "expert", f"预期 OP100/MC100.skill_level=expert，实际 {skill1!r}"
        assert primary1 == "yes", f"预期 OP100/MC100.is_primary=yes，实际 {primary1!r}"

        skill2, primary2 = _fetch_link(conn, "OP200", "MC200")
        assert skill2 == "expert", f"预期 OP200/MC200.skill_level=expert，实际 {skill2!r}"
        assert primary2 == "no", f"预期 OP200/MC200.is_primary=no，实际 {primary2!r}"
    finally:
        conn.close()
