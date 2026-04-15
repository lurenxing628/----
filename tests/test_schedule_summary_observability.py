from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, cast

from core.infrastructure.database import ensure_schema, get_connection

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"



def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)



def _insert_history(db_path: str, *, version: int, result_summary: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version, "priority_first", 0, 0, "success", result_summary, "pytest"),
        )
        conn.commit()
    finally:
        conn.close()



def _capture_warning_logs(app, monkeypatch):
    logged = []

    def _fake_warning(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    return logged



def test_dashboard_logs_warning_when_latest_result_summary_is_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=1, result_summary="{invalid json")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/")

    assert resp.status_code == 200
    assert any("首页 result_summary 解析失败（version=1" in item for item in warnings)



def test_scheduler_batches_keeps_latest_history_when_summary_is_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=2, result_summary="{invalid json")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/scheduler/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "版本：<strong>v2</strong>" in body
    assert "还没有排过产" not in body
    assert any("排产页 result_summary 解析失败（version=2" in item for item in warnings)



def test_system_history_logs_warning_for_selected_and_list_summary_parse_failures(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=3, result_summary="{selected broken")
    _insert_history(db_path, version=4, result_summary="{list broken")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/system/history?version=3")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "版本详情：v3" in body
    assert "最近排产记录" in body
    assert any("排产历史页 result_summary 解析失败（version=3, source=selected" in item for item in warnings)
    assert any("排产历史页 result_summary 解析失败（version=4, source=list" in item for item in warnings)



def test_scheduler_analysis_logs_warning_for_selected_and_trend_summary_parse_failures(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=5, result_summary="{analysis broken")
    client = app.test_client()
    warnings = _capture_warning_logs(app, monkeypatch)

    resp = client.get("/scheduler/analysis?version=5")

    assert resp.status_code == 200
    assert any("排产分析页 result_summary 解析失败（version=5, source=selected" in item for item in warnings)
    assert any("排产分析页 result_summary 解析失败（version=5, source=trend" in item for item in warnings)


def test_dashboard_accepts_preparsed_result_summary_dict(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    import web.bootstrap.request_services as request_services_mod
    import web.routes.dashboard as route_mod

    summary = {"overdue_batches": {"count": "3"}}

    class _StubBatchService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def list(self, status=None):
            return []

    class _StubHistoryService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def list_recent(self, limit=1):
            return [SimpleNamespace(version=9, result_summary=summary)]

    monkeypatch.setattr(request_services_mod, "BatchService", _StubBatchService)
    monkeypatch.setattr(request_services_mod, "ScheduleHistoryQueryService", _StubHistoryService)
    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    with app.test_request_context("/"):
        app.preprocess_request()
        ctx = cast(Dict[str, Any], route_mod.index())

    assert ctx["latest_summary"] == summary
    assert ctx["overdue_count"] == 3


def test_scheduler_batches_accepts_preparsed_result_summary_dict(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    import web.bootstrap.request_services as request_services_mod
    import web.routes.scheduler_batches as route_mod

    summary = {"warnings": ["告警一", "告警二", "告警一"]}

    class _StubBatchService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def list(self, status=None):
            return []

    class _StubConfigService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def get_snapshot(self):
            return SimpleNamespace(enforce_ready_default="no")

        def get_available_strategies(self):
            return []

        def list_presets(self):
            return []

        def get_active_preset(self):
            return None

        def get_active_preset_reason(self):
            return "当前以手动设置为准。"

    class _StubHistoryItem:
        def to_dict(self):
            return {"version": 2, "result_summary": summary}

    class _StubHistoryService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def list_recent(self, limit=1):
            return [_StubHistoryItem()]

    monkeypatch.setattr(request_services_mod, "BatchService", _StubBatchService)
    monkeypatch.setattr(request_services_mod, "ConfigService", _StubConfigService)
    monkeypatch.setattr(request_services_mod, "ScheduleHistoryQueryService", _StubHistoryService)
    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    with app.test_request_context("/scheduler/"):
        app.preprocess_request()
        ctx = cast(Dict[str, Any], route_mod.batches_page())

    assert ctx["latest_summary"] == summary
    assert ctx["latest_warning_preview"] == ["告警一", "告警二"]
    assert ctx["latest_warning_total"] == 2
    assert ctx["latest_warning_hidden_count"] == 0


def test_system_history_accepts_preparsed_result_summary_dict(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    import web.bootstrap.request_services as request_services_mod
    import web.routes.system_history as route_mod

    summary = {"algo": {"metrics": {"overdue_count": 1}}}

    class _StubHistoryItem:
        def __init__(self, version: int):
            self.version = int(version)

        def to_dict(self):
            return {"version": self.version, "result_summary": summary}

    class _StubHistoryService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            self.logger = logger
            self.op_logger = op_logger

        def list_versions(self, limit=30):
            return [{"version": 3}]

        def get_by_version(self, version):
            return _StubHistoryItem(int(version))

        def list_recent(self, limit=20):
            return [_StubHistoryItem(3)]

    monkeypatch.setattr(request_services_mod, "ScheduleHistoryQueryService", _StubHistoryService)
    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    with app.test_request_context("/system/history?version=3"):
        app.preprocess_request()
        ctx = cast(Dict[str, Any], route_mod.history_page())

    assert ctx["selected_summary"] == summary
    items = cast(List[Dict[str, Any]], ctx["items"])
    assert items[0]["result_summary_obj"] == summary


def test_scheduler_analysis_viewmodel_accepts_preparsed_result_summary_dict() -> None:
    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    summary = {
        "algo": {
            "metrics": {
                "overdue_count": 1,
                "total_tardiness_hours": 0,
                "weighted_tardiness_hours": 0,
                "makespan_hours": 1,
                "makespan_internal_hours": 1,
                "changeover_count": 0,
                "machine_util_avg": 0,
                "operator_util_avg": 0,
            }
        }
    }
    item = {"version": 7, "result_summary": summary}

    ctx = build_analysis_context(selected_ver=7, raw_hist=[item], selected_item=item)

    assert ctx["selected_summary"] == summary
    assert ctx["trend_rows"][0]["version"] == 7
