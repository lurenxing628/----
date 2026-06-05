"""回归测试：首页“超期批次”统计卡片对脏 result_summary 容错——当 overdue_batches.count 是非整数（如 "2.9"）时显示“数据不足”并提示“排产摘要里的超期批次数不是整数”，绝不把脏值泄漏或伪装成 0；overdue_batches 为 list 结构时仍能正确数出超期数为 1。"""

from __future__ import annotations

import importlib
import os
import re
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


def _extract_overdue_count_text(html: str) -> str:
    m = re.search(r"超期批次</div>\s*<div class=['\"]stat-card-value danger['\"]>\s*([^<]+)\s*</div>", html, re.S)
    if not m:
        raise RuntimeError(f"未找到首页“超期批次”统计卡片，body={html[:500]!r}")
    return m.group(1).strip()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_dashboard_overdue_")
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
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "priority_first",
                0,
                0,
                "success",
                '{"overdue_batches":{"count":"2.9","items":[]}}',
                "reg",
            ),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P1", "测试零件"))
        conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES (?, ?, ?)", ("B1", "P1", 1))
        op_cursor = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES (?, ?, ?, ?)",
            ("OP1", "B1", 10, "测试工序"),
        )
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?)",
            (op_cursor.lastrowid, "2026-05-06 08:00:00", "2026-05-06 10:00:00", "unlocked", 2),
        )
        conn.commit()
    finally:
        conn.close()

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()
    # 固定 V1 模式，确保首页包含统计卡片结构
    try:
        client.set_cookie("aps_ui_mode", "v1", domain="localhost")
    except TypeError:
        client.set_cookie("localhost", "aps_ui_mode", "v1")

    resp = client.get("/")
    _assert_status(resp, "GET /")

    html = resp.data.decode("utf-8", errors="ignore")
    if "Internal Server Error" in html or "Traceback" in html:
        raise RuntimeError("脏数据容错失败：首页出现错误页内容")
    if "2.9" in html:
        raise RuntimeError("脏数据容错失败：脏值泄漏到首页展示")
    if _extract_overdue_count_text(html) != "数据不足":
        raise RuntimeError("脏数据容错失败：count='2.9' 时首页超期数不能伪装成 0")
    if "排产摘要里的超期批次数不是整数" not in html:
        raise RuntimeError("脏数据容错失败：count='2.9' 应显示数据问题提示")

    # 追加历史 list 结构，首页应兼容并展示正确数量
    conn = get_connection(test_db)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "priority_first",
                0,
                0,
                "success",
                '{"overdue_batches":[{"batch_id":"B1"}]}',
                "reg",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    resp2 = client.get("/")
    _assert_status(resp2, "GET / (list overdue_batches)")
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if _extract_overdue_count_text(html2) != "1":
        raise RuntimeError("list 结构兼容失败：首页超期数应为 1")

    print("OK")


if __name__ == "__main__":
    main()
