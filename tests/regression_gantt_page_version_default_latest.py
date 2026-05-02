from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

from core.infrastructure.errors import BusinessError, ErrorCode

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(
    tmp_path,
    monkeypatch,
    *,
    with_history: bool = True,
    orphan_schedule: bool = False,
    result_status: str = "success",
    result_summary=None,
    extra_histories=None,
):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    if with_history:
        summary_obj = {} if result_summary is None else result_summary
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (7, "greedy", 0, 0, result_status, json.dumps(summary_obj, ensure_ascii=False), "pytest"),
        )
        for raw_history in list(extra_histories or []):
            extra_summary = dict(raw_history.get("result_summary") or {})
            conn.execute(
                "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    int(raw_history.get("version")),
                    raw_history.get("strategy") or "greedy",
                    0,
                    0,
                    raw_history.get("result_status") or "success",
                    json.dumps(extra_summary, ensure_ascii=False),
                    "pytest",
                ),
            )
    if orphan_schedule:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, version) VALUES (?, ?, ?, ?, ?, ?)",
            (999, "M-ORPHAN", "OP-ORPHAN", "2026-03-02 08:00:00", "2026-03-02 09:00:00", 1),
        )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_gantt_page_version_default_latest(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02")
    assert page_resp.status_code == 200
    assert "第 7 版" in page_resp.get_data(as_text=True)

    page_latest_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=latest")
    assert page_latest_resp.status_code == 200
    assert "第 7 版" in page_latest_resp.get_data(as_text=True)

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02")
    assert data_resp.status_code == 200
    payload = json.loads(data_resp.get_data(as_text=True) or "{}")
    assert payload.get("success") is True, payload
    assert int((payload.get("data") or {}).get("version") or 0) == 7

    invalid_page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=0")
    invalid_page_html = invalid_page_resp.get_data(as_text=True)
    assert invalid_page_resp.status_code == 400
    assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in invalid_page_html

    invalid_data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=-1")
    invalid_payload = invalid_data_resp.get_json()
    assert invalid_data_resp.status_code == 400
    assert invalid_payload["success"] is False
    assert invalid_payload["error"]["message"] == "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。"

    missing_page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=999")
    missing_page_html = missing_page_resp.get_data(as_text=True)
    assert missing_page_resp.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in missing_page_html
    assert "data-version=\"None\"" not in missing_page_html


def test_gantt_no_history_does_not_synthesize_v1_even_with_orphan_schedule(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False, orphan_schedule=True)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02")
    page_html = page_resp.get_data(as_text=True)
    assert page_resp.status_code == 200
    assert "暂无排产版本" in page_html
    assert "第 1 版" not in page_html
    assert "第 0 版" not in page_html
    assert "第 None 版" not in page_html
    assert "value=\"None\"" not in page_html
    assert "data-version=\"None\"" not in page_html

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02")
    payload = data_resp.get_json()
    data = payload.get("data") or {}
    assert data_resp.status_code == 200
    assert payload.get("success") is True, payload
    assert data.get("status") == "no_history", data
    assert data.get("version") is None, data
    assert data.get("tasks") == [], data

    missing_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=1")
    missing_payload = missing_resp.get_json()
    assert missing_resp.status_code == 404
    assert missing_payload["success"] is False


def test_gantt_page_selected_version_label_includes_simulated_completion_status(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="simulated",
        result_summary={"completion_status": "partial", "counts": {"op_count": 3, "scheduled_ops": 2, "failed_ops": 1}},
    )
    client = app.test_client()

    response = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=7")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "v7 · 部分成功" in html


def test_gantt_page_non_selected_version_option_uses_completion_status_label(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="success",
        result_summary={"completion_status": "success"},
        extra_histories=[
            {
                "version": 6,
                "result_status": "simulated",
                "result_summary": {"completion_status": "partial", "counts": {"op_count": 3, "scheduled_ops": 2, "failed_ops": 1}},
            }
        ],
    )
    client = app.test_client()

    response = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=7")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "v6" in html
    assert "v6 · 部分成功" in html


def test_gantt_data_uses_app_error_http_mapping(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    def _raise_not_found(self, **_kwargs):
        raise BusinessError(ErrorCode.NOT_FOUND, "甘特图版本不存在")

    monkeypatch.setattr(GanttService, "get_gantt_tasks", _raise_not_found)

    response = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=7")

    payload = response.get_json()
    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.NOT_FOUND.value
    assert payload["error"]["message"] == "甘特图版本不存在"


def test_gantt_data_unexpected_error_uses_unified_unknown_error_contract(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    def _raise_bug(self, **_kwargs):
        raise RuntimeError("gantt exploded")

    monkeypatch.setattr(GanttService, "get_gantt_tasks", _raise_bug)

    response = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=7")

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.UNKNOWN_ERROR.value
    assert payload["error"]["message"] == "甘特图数据生成失败，请稍后重试。"
