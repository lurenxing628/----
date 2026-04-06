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


def _make_downtime_rows(count: int) -> List[Dict[str, Any]]:
    return [
        {
            "machine_id": f"MC{i:03d}",
            "machine_name": f"设备{i}",
            "downtime_hours": 2.0,
            "downtime_count": 1,
            "schedule_overlap_hours": 1.0,
            "schedule_overlap_count": 1,
        }
        for i in range(1, count + 1)
    ]


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_regression_report_export_reject_")
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
    original_downtime_impact = ReportEngine.downtime_impact

    try:
        report_engine_cls = cast(Any, ReportEngine)
        report_engine_cls.EXPORT_DIRECT_MAX_ROWS = 2
        report_engine_cls.EXPORT_STREAM_MAX_ROWS = 4

        def fake_downtime_impact(self, version: int, start_date: Any, end_date: Any) -> Dict[str, Any]:
            return {
                "version": int(version),
                "start_date": str(start_date),
                "end_date": str(end_date),
                "machines": _make_downtime_rows(5),
            }

        ReportEngine.downtime_impact = fake_downtime_impact

        resp = client.get(
            "/reports/downtime/export?version=7&start_date=2026-01-01&end_date=2026-01-07",
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 400:
            body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
            raise RuntimeError(f"大范围导出未被拒绝：status={resp.status_code} body={body[:500]}")

        payload = resp.get_json(silent=True) or {}
        error = payload.get("error") or {}
        if error.get("code") != "1001":
            raise RuntimeError(f"错误码异常：{error!r}")
        message = str(error.get("message") or "")
        if "缩小范围" not in message or "后台" not in message:
            raise RuntimeError(f"错误消息未明确提示缩小范围或改走后台：{message!r}")
        details = error.get("details") or {}
        if details.get("mode") != "reject_need_async":
            raise RuntimeError(f"拒绝模式未透出：{details!r}")
        if int(details.get("estimated_rows") or 0) != 5:
            raise RuntimeError(f"拒绝行数估计异常：{details!r}")
        if details.get("report_name") != "停机影响统计":
            raise RuntimeError(f"拒绝报表名异常：{details!r}")

        print("OK")
    finally:
        ReportEngine.EXPORT_DIRECT_MAX_ROWS = original_direct_max
        ReportEngine.EXPORT_STREAM_MAX_ROWS = original_stream_max
        ReportEngine.downtime_impact = original_downtime_impact


if __name__ == "__main__":
    main()
