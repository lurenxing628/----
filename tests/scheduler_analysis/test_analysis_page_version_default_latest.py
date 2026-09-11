"""回归测试：/scheduler/analysis 页面在 version 缺省/为空/latest 时默认展示最新版本号（v7），version=abc 返回 400 且只给口语化提示不泄露技术细节，version=999 不存在时保留版本趋势且不伪造选中项，并校验下拉用完工状态标签与冻结窗口降级展示。"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

from tests._support.excel_templates import point_env_at_shared
from tests._support.legacy_report_contract import (
    analysis_read_context,
    assert_plan_navigation,
    assert_rejected,
    get_unchanged,
    saved_summary_display,
)
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch, *, result_status: str = "success", result_summary=None):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    summary_obj = (
        {"algo": {"metrics": {"overdue_count": 1, "makespan_hours": 8}}, "warnings": []}
        if result_summary is None
        else result_summary
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (7, "greedy", 0, 0, result_status, json.dumps(summary_obj, ensure_ascii=False), "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_analysis_page_version_default_latest(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    db_path = tmp_path / "aps_test.db"
    contexts = []
    for suffix in ("", "?version=", "?version=latest"):
        response = get_unchanged(client, "/scheduler/analysis" + suffix, db_path)
        contexts.append(assert_plan_navigation(response, db_path, version=7))
    assert contexts[0] == contexts[1] == contexts[2]
    invalid = get_unchanged(client, "/scheduler/analysis?version=abc", db_path)
    assert_rejected(invalid, forbidden=("abc", "version 不合法", "期望整数"))


def test_analysis_missing_version_keeps_trends_visible_without_fake_selected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    db_path = tmp_path / "aps_test.db"
    response = get_unchanged(app.test_client(), "/scheduler/analysis?version=999", db_path)
    assert response.status_code == 404 and "Location" not in response.headers
    assert 'value="999"' not in response.get_data(as_text=True)
    read = analysis_read_context(app, db_path, "999")
    assert read.selected_item is None
    assert read.selected_history_resolution["history_missing"] is True
    assert "v999 无对应排产历史" in read.selected_history_resolution["message"]
    assert {item["version"] for item in read.raw_hist} == {7}


def test_analysis_version_dropdown_uses_completion_status_label(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="simulated",
        result_summary={"completion_status": "partial", "algo": {"metrics": {"overdue_count": 1}}},
    )
    client = app.test_client()

    db_path = tmp_path / "aps_test.db"
    response = get_unchanged(client, "/scheduler/analysis?version=7", db_path)
    assert_plan_navigation(response, db_path, version=7)
    original, display = saved_summary_display(db_path, 7)
    assert original[0] == "simulated"
    assert display["result_status_label"] == "模拟排产 / 部分成功"
    read = analysis_read_context(app, db_path, "7")
    assert read.versions[0]["result_status_label"] == "模拟排产 / 部分成功"


def test_analysis_page_shows_degraded_freeze_window_when_config_defaults_to_disabled(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        result_summary={
            "algo": {
                "metrics": {"overdue_count": 0, "makespan_hours": 8},
                "freeze_window": {
                    "enabled": "no",
                    "days": 0,
                    "frozen_op_count": 0,
                    "frozen_batch_count": 0,
                    "frozen_batch_ids_sample": [],
                    "freeze_state": "degraded",
                    "freeze_applied": False,
                    "freeze_degradation_codes": ["freeze_seed_unavailable"],
                    "degraded": True,
                    "degradation_reason": "冻结窗口配置读取降级",
                },
            },
            "degradation_events": [
                {
                    "code": "freeze_window_degraded",
                    "scope": "schedule.summary.freeze_window",
                    "field": "freeze_window",
                    "message": "冻结窗口配置读取降级",
                    "count": 1,
                }
            ],
            "warnings": [],
        },
    )
    client = app.test_client()

    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    db_path = tmp_path / "aps_test.db"
    response = get_unchanged(client, "/scheduler/analysis?version=7", db_path)
    assert_plan_navigation(response, db_path, version=7)
    read = analysis_read_context(app, db_path, "7")
    ctx = build_analysis_context(selected_ver=7, raw_hist=read.raw_hist, selected_item=read.selected_item)
    assert ctx["freeze_display"]["state"] == "degraded"
    assert ctx["freeze_display"]["state_label"] == "部分未生效"
    assert ctx["freeze_display"]["degraded"] is True
    assert any(item["code"] == "freeze_window_degraded" for item in ctx["summary_degradation_messages"])
