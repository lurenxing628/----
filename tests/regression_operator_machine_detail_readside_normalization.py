from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
from typing import Optional, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_detail_readside_norm_")
    test_db = os.path.join(root, "aps_test.db")
    test_logs = os.path.join(root, "logs")
    test_backups = os.path.join(root, "backups")
    test_templates = os.path.join(root, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
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

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    resp_equipment = client.get("/equipment/MC100")
    _assert_status(resp_equipment, "GET /equipment/MC100")
    html_equipment = resp_equipment.data.decode("utf-8", errors="ignore")
    assert _selected_skill_value(html_equipment) == "expert", "设备详情页未将 skilled 归一显示为 expert"
    assert _is_primary_checked(html_equipment, "linkform_0"), "设备详情页未将中文“是”归一显示为勾选"

    resp_personnel = client.get("/personnel/OP200")
    _assert_status(resp_personnel, "GET /personnel/OP200")
    html_personnel = resp_personnel.data.decode("utf-8", errors="ignore")
    assert _selected_skill_value(html_personnel) == "expert", "人员详情页未将 skilled 归一显示为 expert"
    assert not _is_primary_checked(html_personnel, "linkform_0"), "人员详情页未将 off 归一显示为未勾选"

    resp_save_equipment = client.post(
        "/equipment/MC100/link/update",
        data={"operator_id": "OP100", "skill_level": "expert", "is_primary": "yes"},
        follow_redirects=True,
    )
    _assert_status(resp_save_equipment, "POST /equipment/MC100/link/update")

    resp_save_personnel = client.post(
        "/personnel/OP200/link/update",
        data={"machine_id": "MC200", "skill_level": "expert"},
        follow_redirects=True,
    )
    _assert_status(resp_save_personnel, "POST /personnel/OP200/link/update")

    conn = get_connection(test_db)
    try:
        skill1, primary1 = _fetch_link(conn, "OP100", "MC100")
        assert skill1 == "expert", f"预期 OP100/MC100.skill_level=expert，实际 {skill1!r}"
        assert primary1 == "yes", f"预期 OP100/MC100.is_primary=yes，实际 {primary1!r}"

        skill2, primary2 = _fetch_link(conn, "OP200", "MC200")
        assert skill2 == "expert", f"预期 OP200/MC200.skill_level=expert，实际 {skill2!r}"
        assert primary2 == "no", f"预期 OP200/MC200.is_primary=no，实际 {primary2!r}"
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
