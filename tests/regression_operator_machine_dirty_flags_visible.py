from __future__ import annotations

import importlib
import os
import sys
import tempfile


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_operator_machine_dirty_")
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
    from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=test_backups)

    conn = get_connection(test_db)
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
    assert "历史技能等级写法较旧，系统已先按能识别的中文选项处理。" == str((row_invalid.get("dirty_reasons") or {}).get("skill_level") or ""), row_invalid
    assert "历史主操标记写法较旧，系统已先按“否”处理。" == str((row_invalid.get("dirty_reasons") or {}).get("is_primary") or ""), row_invalid

    row_blank = next((item for item in rows if item.get("operator_id") == "OP200" and item.get("machine_id") == "MC201"), None)
    assert row_blank is not None, rows
    assert set(row_blank.get("dirty_fields") or []) == {"skill_level", "is_primary"}, row_blank
    assert "历史技能等级为空，系统已先按“普通”处理。" == str((row_blank.get("dirty_reasons") or {}).get("skill_level") or ""), row_blank
    assert "历史主操标记为空，系统已先按“否”处理。" == str((row_blank.get("dirty_reasons") or {}).get("is_primary") or ""), row_blank

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    resp = client.get("/personnel/OP200")
    _assert_status(resp, "GET /personnel/OP200")
    html = resp.data.decode("utf-8", errors="ignore")

    assert "以下 2 条记录中有部分字段的旧格式已被系统自动修正" in html, html
    assert "涉及字段：" in html, html
    assert "技能等级" in html, html
    assert "主操设备" in html, html
    assert "旧格式已自动修正：历史技能等级写法较旧，系统已先按能识别的中文选项处理。" in html, html
    assert "旧格式已自动修正：历史主操标记写法较旧，系统已先按“否”处理。" in html, html
    assert "旧格式已自动修正：历史技能等级为空，系统已先按“普通”处理。" in html, html
    assert "旧格式已自动修正：历史主操标记为空，系统已先按“否”处理。" in html, html

    print("OK")


if __name__ == "__main__":
    main()
