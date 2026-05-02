from __future__ import annotations

import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_xlsx(resp, name: str, expect_version: int) -> None:
    if resp.status_code != 200:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 200")
    ct = resp.headers.get("Content-Type", "")
    if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in ct:
        raise RuntimeError(f"{name} content-type 异常：{ct}")
    cd = resp.headers.get("Content-Disposition", "")
    if f"v{int(expect_version)}" not in cd:
        raise RuntimeError(f"{name} filename 未包含 v{expect_version}（Content-Disposition={cd!r}）")


def _assert_invalid_version(resp, name: str) -> None:
    from core.services.scheduler.version_resolution import VERSION_ERROR_MESSAGE

    if resp.status_code != 400:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 400")
    body = resp.get_data(as_text=True)
    if VERSION_ERROR_MESSAGE not in body:
        raise RuntimeError(f"{name} 未返回统一版本错误文案：{body[:200]!r}")


def _assert_empty_export(resp, name: str) -> None:
    if resp.status_code != 400:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 400")
    body = resp.get_data(as_text=True)
    if "overdue" in name:
        expected = "当前版本没有可导出的超期结果，请换一个排产版本后再试。"
    else:
        expected = "暂无数据，不能导出。请调整版本或日期范围后再试。"
    if expected not in body:
        raise RuntimeError(f"{name} 未返回空数据不可导出提示：{body[:200]!r}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # 隔离目录，避免污染真实 db/logs/backups/templates_excel
    root = tempfile.mkdtemp(prefix="aps_regression_reports_export_ver_")
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

    # 准备 1 条排产历史，让 latest_version() 有确定值
    conn = get_connection(test_db)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (7, "test", 0, 0, "ok", None, "regression"),
        )
        conn.commit()
    finally:
        conn.close()

    # Flask test_client（不启动 server）
    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    sd = "2026-01-01"
    ed = "2026-01-07"

    # 1) overdue/export
    _assert_empty_export(client.get("/reports/overdue/export"), "GET /reports/overdue/export（missing version）")
    _assert_empty_export(client.get("/reports/overdue/export?version="), "GET /reports/overdue/export（empty version）")
    _assert_empty_export(client.get("/reports/overdue/export?version=latest"), "GET /reports/overdue/export（version=latest）")
    _assert_invalid_version(client.get("/reports/overdue/export?version=abc"), "GET /reports/overdue/export（invalid version）")
    _assert_invalid_version(client.get("/reports/overdue/export?version=0"), "GET /reports/overdue/export（version=0）")

    # 2) utilization/export（需要 start/end）
    _assert_empty_export(
        client.get(f"/reports/utilization/export?start_date={sd}&end_date={ed}"),
        "GET /reports/utilization/export（missing version）",
    )
    _assert_empty_export(
        client.get(f"/reports/utilization/export?version=&start_date={sd}&end_date={ed}"),
        "GET /reports/utilization/export（empty version）",
    )
    _assert_empty_export(
        client.get(f"/reports/utilization/export?version=latest&start_date={sd}&end_date={ed}"),
        "GET /reports/utilization/export（version=latest）",
    )
    _assert_invalid_version(
        client.get(f"/reports/utilization/export?version=abc&start_date={sd}&end_date={ed}"),
        "GET /reports/utilization/export（invalid version）",
    )
    _assert_invalid_version(
        client.get(f"/reports/utilization/export?version=0&start_date={sd}&end_date={ed}"),
        "GET /reports/utilization/export（version=0）",
    )

    # 3) downtime/export（需要 start/end）
    _assert_empty_export(
        client.get(f"/reports/downtime/export?start_date={sd}&end_date={ed}"),
        "GET /reports/downtime/export（missing version）",
    )
    _assert_empty_export(
        client.get(f"/reports/downtime/export?version=&start_date={sd}&end_date={ed}"),
        "GET /reports/downtime/export（empty version）",
    )
    _assert_empty_export(
        client.get(f"/reports/downtime/export?version=latest&start_date={sd}&end_date={ed}"),
        "GET /reports/downtime/export（version=latest）",
    )
    _assert_invalid_version(
        client.get(f"/reports/downtime/export?version=abc&start_date={sd}&end_date={ed}"),
        "GET /reports/downtime/export（invalid version）",
    )
    _assert_invalid_version(
        client.get(f"/reports/downtime/export?version=0&start_date={sd}&end_date={ed}"),
        "GET /reports/downtime/export（version=0）",
    )

    print("OK")


if __name__ == "__main__":
    main()
