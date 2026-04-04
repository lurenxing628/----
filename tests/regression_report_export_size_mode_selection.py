from __future__ import annotations

import os
import sys
import tempfile
from typing import Any, Dict, List, cast


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_xlsx(resp, name: str, expect_version: int) -> None:
    if resp.status_code != 200:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 200，body={body[:500]}")
    ct = resp.headers.get("Content-Type", "")
    if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in ct:
        raise RuntimeError(f"{name} content-type 异常：{ct}")
    cd = resp.headers.get("Content-Disposition", "")
    if f"v{int(expect_version)}" not in cd:
        raise RuntimeError(f"{name} filename 未包含 v{expect_version}（Content-Disposition={cd!r}）")


def _make_overdue_items(count: int) -> List[Dict[str, Any]]:
    return [
        {
            "bucket_label": "已排程超期",
            "batch_id": f"B{i:03d}",
            "part_no": f"P{i:03d}",
            "part_name": f"零件{i}",
            "quantity": 1,
            "due_date": "2026-01-01",
            "finish_time": "2026-01-02 08:00:00",
            "as_of_time": None,
            "delay_hours": 8.0,
            "delay_days": 0.33,
        }
        for i in range(1, count + 1)
    ]


def _make_utilization_rows(count: int) -> List[Dict[str, Any]]:
    return [
        {
            "machine_id": f"MC{i:03d}",
            "machine_name": f"设备{i}",
            "hours": 8.0,
            "task_count": 1,
            "capacity_hours": 16.0,
            "utilization": 0.5,
        }
        for i in range(1, count + 1)
    ]


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_regression_report_export_mode_")
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
            (7, "test", 0, 0, "ok", None, "regression"),
        )
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    from core.services.report.report_engine import ReportEngine

    original_direct_max = ReportEngine.EXPORT_DIRECT_MAX_ROWS
    original_stream_max = ReportEngine.EXPORT_STREAM_MAX_ROWS
    original_overdue_batches = ReportEngine.overdue_batches
    original_utilization = ReportEngine.utilization

    try:
        report_engine_cls = cast(Any, ReportEngine)
        report_engine_cls.EXPORT_DIRECT_MAX_ROWS = 2
        report_engine_cls.EXPORT_STREAM_MAX_ROWS = 4

        def fake_overdue_batches(self, version: int) -> Dict[str, Any]:
            items = _make_overdue_items(2)
            return {
                "version": int(version),
                "count": len(items),
                "scheduled_count": len(items),
                "unscheduled_count": 0,
                "as_of_time": "2026-01-02 08:00:00",
                "items": items,
                "scheduled_items": list(items),
                "unscheduled_items": [],
            }

        def fake_utilization(self, version: int, start_date: Any, end_date: Any) -> Dict[str, Any]:
            return {
                "version": int(version),
                "start_date": str(start_date),
                "end_date": str(end_date),
                "capacity_hours_per_resource": 16.0,
                "machines": _make_utilization_rows(3),
                "operators": [],
            }

        ReportEngine.overdue_batches = fake_overdue_batches
        ReportEngine.utilization = fake_utilization

        overdue_resp = client.get("/reports/overdue/export?version=7")
        _assert_xlsx(overdue_resp, "GET /reports/overdue/export", 7)
        overdue_mode = overdue_resp.headers.get("X-APS-Report-Export-Mode", "")
        if overdue_mode != "direct":
            raise RuntimeError(f"超期清单导出模式错误：{overdue_mode!r}")
        overdue_rows = overdue_resp.headers.get("X-APS-Report-Estimated-Rows", "")
        if overdue_rows != "2":
            raise RuntimeError(f"超期清单导出行数估计错误：{overdue_rows!r}")

        util_resp = client.get("/reports/utilization/export?version=7&start_date=2026-01-01&end_date=2026-01-07")
        _assert_xlsx(util_resp, "GET /reports/utilization/export", 7)
        util_mode = util_resp.headers.get("X-APS-Report-Export-Mode", "")
        if util_mode != "stream":
            raise RuntimeError(f"资源负荷导出模式错误：{util_mode!r}")
        util_rows = util_resp.headers.get("X-APS-Report-Estimated-Rows", "")
        if util_rows != "3":
            raise RuntimeError(f"资源负荷导出行数估计错误：{util_rows!r}")

        print("OK")
    finally:
        ReportEngine.EXPORT_DIRECT_MAX_ROWS = original_direct_max
        ReportEngine.EXPORT_STREAM_MAX_ROWS = original_stream_max
        ReportEngine.overdue_batches = original_overdue_batches
        ReportEngine.utilization = original_utilization


if __name__ == "__main__":
    main()
