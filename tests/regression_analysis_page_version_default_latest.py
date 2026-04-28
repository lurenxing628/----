from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch, *, result_status: str = "success", result_summary=None):
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

    resp = client.get("/scheduler/analysis")
    assert resp.status_code == 200
    assert "版本概览：v7" in resp.get_data(as_text=True)

    resp_latest = client.get("/scheduler/analysis?version=latest")
    assert resp_latest.status_code == 200
    assert "版本概览：v7" in resp_latest.get_data(as_text=True)

    resp_invalid = client.get("/scheduler/analysis?version=abc")
    invalid_html = resp_invalid.get_data(as_text=True)
    assert resp_invalid.status_code == 400
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in invalid_html
    assert "version 不合法" not in invalid_html
    assert "期望整数" not in invalid_html


def test_analysis_missing_version_keeps_trends_visible_without_fake_selected(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=999")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "v999 无对应排产历史" in html
    assert "版本概览：v999" not in html
    assert 'value="999"' not in html
    assert "版本趋势（最近 1 个有指标的版本）" in html


def test_analysis_version_dropdown_uses_completion_status_label(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="simulated",
        result_summary={"completion_status": "partial", "algo": {"metrics": {"overdue_count": 1}}},
    )
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=7")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.count("模拟排产 / 部分成功") >= 2


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

    response = client.get("/scheduler/analysis?version=7")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "冻结窗口：已降级" in html
    assert "当前状态：已降级" in html
    assert "冻结窗口约束已降级" in html
    assert "冻结窗口：未启用" not in html
