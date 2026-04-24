from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from unittest import mock


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

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.common.build_outcome import BuildOutcome
    from core.services.common.degradation import DegradationCollector

    root = tempfile.mkdtemp(prefix="aps_reg_gantt_calendar_failed_")
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

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=test_backups)

    conn = get_connection(test_db)
    try:
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (3, "greedy", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()
    finally:
        conn.close()

    def _calendar_failed(*_args, **_kwargs):
        collector = DegradationCollector()
        collector.add(
            code="calendar_load_failed",
            scope="gantt.calendar_days",
            field="calendar_days",
            message="工作日历加载失败，已降级为空列表。",
            sample="RuntimeError",
        )
        return BuildOutcome.from_collector([], collector, empty_reason="calendar_load_failed")

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    with mock.patch("core.services.scheduler.gantt_service.build_calendar_days", side_effect=_calendar_failed):
        page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=3")
        _assert_status(page_resp, "GET /scheduler/gantt")
        html = page_resp.data.decode("utf-8", errors="ignore")
        assert 'id="ganttDegradationWarning"' in html, html
        assert "工作日历加载失败，当前不显示假期/停工背景标注。" in html, html

        data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=3")
        _assert_status(data_resp, "GET /scheduler/gantt/data")
        payload = json.loads(data_resp.data.decode("utf-8", errors="ignore") or "{}")
        assert payload.get("success") is True, payload
        data = dict(payload.get("data") or {})
        assert data.get("degraded") is True, data
        assert data.get("empty_reason") == "calendar_load_failed", data
        counters = dict(data.get("degradation_counters") or {})
        assert int(counters.get("calendar_load_failed") or 0) == 1, counters
        events = list(data.get("degradation_events") or [])
        assert any(str(evt.get("code") or "") == "calendar_load_failed" for evt in events), events
        assert "RuntimeError" not in str(events)
        assert all("sample" not in evt for evt in events if isinstance(evt, dict)), events

    gantt_boot_js = open(os.path.join(repo_root, "static", "js", "gantt_boot.js"), "r", encoding="utf-8").read()
    gantt_contract_js = open(os.path.join(repo_root, "static", "js", "gantt_contract.js"), "r", encoding="utf-8").read()
    assert "ganttDegradationWarning" in gantt_boot_js, "gantt_boot.js 未接入页面退化提示节点"
    assert "buildDegradationMessages" in gantt_boot_js, "gantt_boot.js 未接入共享退化提示构造器"
    assert "calendar_load_failed" in gantt_contract_js, "gantt_contract.js 未识别 calendar_load_failed"

    print("OK")


if __name__ == "__main__":
    main()
