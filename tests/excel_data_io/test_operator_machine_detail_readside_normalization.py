"""旧详情保持身份跳转；保留的关联下载归一显示，link/update 写回规范值且互不串写。"""

from __future__ import annotations

from typing import Optional, Tuple

from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from tests._support.legacy_http import canonical_resource, xlsx_download_rows
from tests._support.sqlite_snapshot import table_rows


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


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
        before = table_rows(conn, "OperatorMachine")
    finally:
        conn.close()

    resp_equipment = app_client.get("/equipment/MC100")
    canonical_resource(app_client, resp_equipment, "machine", "MC100")

    resp_personnel = app_client.get("/personnel/OP200")
    canonical_resource(app_client, resp_personnel, "operator", "OP200")
    equipment_rows = xlsx_download_rows(app_client.get("/equipment/excel/links/export"))
    personnel_rows = xlsx_download_rows(app_client.get("/personnel/excel/links/export"))
    assert len(equipment_rows) == len(personnel_rows) == 2
    first = next(row for row in equipment_rows if row["设备编号"] == "MC100")
    second = next(row for row in personnel_rows if row["工号"] == "OP200")
    assert first["工号"] == "OP100" and second["设备编号"] == "MC200"
    assert first["技能等级"] == second["技能等级"] == "熟练"
    assert first["主操设备"] == "是" and second["主操设备"] == "否"
    conn = get_connection(db_path)
    try:
        links = {(row["operator_id"], row["machine_id"]): row for row in OperatorMachineQueryService(conn).list_simple_rows()}
        assert links[("OP100", "MC100")]["skill_level"] == links[("OP200", "MC200")]["skill_level"] == "expert"
        assert links[("OP100", "MC100")]["is_primary"] == "yes"
        assert links[("OP200", "MC200")]["is_primary"] == "no"
        assert table_rows(conn, "OperatorMachine") == before
    finally:
        conn.close()

    resp_save_equipment = app_client.post(
        "/equipment/MC100/link/update",
        data={"operator_id": "OP100", "skill_level": "expert", "is_primary": "yes"},
        follow_redirects=True,
    )
    _assert_status(resp_save_equipment, "POST /equipment/MC100/link/update")
    assert len(resp_save_equipment.history) == 2
    assert resp_save_equipment.history[0].status_code == 302
    assert resp_save_equipment.history[0].headers["Location"] == "/equipment/MC100"
    canonical_resource(app_client, resp_save_equipment.history[1], "machine", "MC100")
    conn = get_connection(db_path)
    try:
        assert _fetch_link(conn, "OP200", "MC200") == ("skilled", "off")
    finally:
        conn.close()

    resp_save_personnel = app_client.post(
        "/personnel/OP200/link/update",
        data={"machine_id": "MC200", "skill_level": "expert"},
        follow_redirects=True,
    )
    _assert_status(resp_save_personnel, "POST /personnel/OP200/link/update")
    assert len(resp_save_personnel.history) == 2
    assert resp_save_personnel.history[0].status_code == 302
    assert resp_save_personnel.history[0].headers["Location"] == "/personnel/OP200"
    canonical_resource(app_client, resp_save_personnel.history[1], "operator", "OP200")

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
