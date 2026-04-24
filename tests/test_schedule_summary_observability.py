from __future__ import annotations

import importlib
import sys
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

    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)

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

        def get_preset_display_state(self, readonly=True, current_snapshot=None):
            return {
                "presets": [],
                "active_preset": None,
                "active_preset_reason": "当前以手动设置为准。",
                "active_preset_missing": True,
                "active_preset_reason_missing": False,
                "current_config_state": {
                    "state": "custom",
                    "degraded": False,
                    "provenance_missing": False,
                    "baseline_key": None,
                    "baseline_label": "自定义",
                    "baseline_source": "custom",
                },
                "readonly": bool(readonly),
            }

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
    assert ctx["latest_warning_preview"] == []
    assert ctx["latest_warning_total"] == 2
    assert ctx["latest_warning_hidden_count"] == 2


def test_scheduler_batches_surfaces_current_config_state_and_other_degradation_messages(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    import web.bootstrap.request_services as request_services_mod
    import web.routes.scheduler_batches as route_mod

    summary = {
        "warnings": ["告警一"],
        "degraded_success": True,
        "degraded_causes": ["merge_context_degraded"],
        "degradation_events": [
            {"code": "merge_context_degraded", "message": "组合并上下文缺失，已降级。", "count": 1},
            {"code": "invalid_due_date", "message": "发现 2 个批次交期非法，已按空交期处理。", "count": 2},
            {"code": "ortools_warmstart_failed", "message": "OR-Tools 预热失败，已回退常规求解。", "count": 1},
        ],
        "algo": {
            "objective": "min_overdue",
            "config_snapshot": {"objective": "min_overdue"},
        },
    }

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
            return SimpleNamespace(
                enforce_ready_default="yes",
                auto_assign_persist="yes",
                degradation_events=(
                    {
                        "code": "invalid_choice",
                        "scope": "scheduler.config_snapshot",
                        "field": "enforce_ready_default",
                        "message": "enforce_ready_default defaulted to yes",
                    },
                    {
                        "code": "invalid_choice",
                        "scope": "scheduler.config_snapshot",
                        "field": "auto_assign_persist",
                        "message": "auto_assign_persist defaulted to yes",
                    },
                ),
            )

        def get_available_strategies(self):
            return []

        def list_presets(self):
            return []

        def get_active_preset(self):
            return "默认-稳定"

        def get_active_preset_reason(self):
            return None

        def get_preset_display_state(self, readonly=True, current_snapshot=None):
            return {
                "presets": [],
                "active_preset": "默认-稳定",
                "active_preset_reason": None,
                "active_preset_missing": False,
                "active_preset_reason_missing": False,
                "current_config_state": {
                    "state": "degraded",
                    "degraded": True,
                    "provenance_missing": False,
                    "baseline_key": "默认-稳定",
                    "baseline_label": "默认-稳定",
                    "baseline_source": "builtin",
                },
                "readonly": bool(readonly),
            }

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

    assert ctx["current_config_state"]["state"] == "degraded"
    assert ctx["current_config_state"]["degraded"] is True
    assert ctx["config_degraded_fields"] == ["enforce_ready_default"]
    assert ctx["config_hidden_warnings"]
    assert ctx["latest_auto_assign_persist_state"]["value"] == "unknown"
    assert ctx["latest_auto_assign_persist_state"]["enabled"] is None
    assert ctx["latest_summary_display"]["primary_degradation"]["details"] == [
        "组合并语义已降级",
        "交期数据已降级（2）",
        "预热已降级",
    ]
    assert ctx["latest_other_degradation_messages"] == []


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
