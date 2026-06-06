from __future__ import annotations

import json
import os
from unittest import mock


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def test_gantt_calendar_load_failed_degraded(app_client, db_path, repo_root) -> None:
    from core.infrastructure.database import get_connection
    from core.services.common.build_outcome import BuildOutcome
    from core.services.common.degradation import DegradationCollector

    conn = get_connection(db_path)
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
            message="工作日历加载失败，当前不显示假期/停工背景标注。",
            sample="RuntimeError",
        )
        return BuildOutcome.from_collector([], collector, empty_reason="calendar_load_failed")

    client = app_client

    with mock.patch("core.services.scheduler.gantt_service.build_calendar_days", side_effect=_calendar_failed):
        page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=3")
        _assert_status(page_resp, "GET /scheduler/gantt")
        html = page_resp.data.decode("utf-8", errors="ignore")
        assert 'id="ganttDegradationWarning"' in html, html
        assert "工作日历加载失败，当前不显示假期/停工背景标注。" not in html, html

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

    gantt_boot_js = open(os.path.join(str(repo_root), "static", "js", "gantt_boot.js"), "r", encoding="utf-8").read()
    gantt_contract_js = open(os.path.join(str(repo_root), "static", "js", "gantt_contract.js"), "r", encoding="utf-8").read()
    assert "ganttDegradationWarning" in gantt_boot_js, "gantt_boot.js 未接入页面退化提示节点"
    assert "buildDegradationMessages" in gantt_boot_js, "gantt_boot.js 未接入共享退化提示构造器"
    assert "calendar_load_failed" in gantt_contract_js, "gantt_contract.js 未识别 calendar_load_failed"
