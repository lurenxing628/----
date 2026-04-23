from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _WeekRange:
    week_start_date = date(2026, 4, 13)
    week_end_date = date(2026, 4, 19)


class _HistoryItem:
    def __init__(self, version: int, summary):
        self.version = int(version)
        self._summary = summary

    def to_dict(self):
        return {
            "version": self.version,
            "schedule_time": "2026-04-13 08:00:00",
            "strategy": "priority_first",
            "result_status": "partial",
            "result_summary": self._summary,
        }


class _HistoryServiceStub:
    def __init__(self, summary, *, missing_versions=None):
        self.summary = summary
        self.version_limits = []
        self.version_queries = []
        self.missing_versions = {int(item) for item in list(missing_versions or [])}

    def list_versions(self, limit=30):
        self.version_limits.append(limit)
        return [{"version": 3, "schedule_time": "2026-04-13 08:00:00", "strategy": "priority_first", "result_status": "partial"}]

    def get_by_version(self, version):
        self.version_queries.append(int(version))
        if int(version) in self.missing_versions:
            return None
        return _HistoryItem(int(version), self.summary)


class _GanttServiceStub:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def get_latest_version_or_1(self):
        return 3

    def resolve_week_range(self, **_kwargs):
        return _WeekRange()

    def get_week_plan_rows(self, **kwargs):
        return {
            "rows": list(self.rows),
            "version": int(kwargs.get("version") or 3),
            "week_start": "2026-04-13",
            "week_end": "2026-04-19",
        }


def _build_app(monkeypatch, history_service: _HistoryServiceStub, *, gantt_service=None) -> Flask:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    import web.routes.scheduler_week_plan as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-week-plan-observability"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(
            gantt_service=gantt_service or _GanttServiceStub(),
            schedule_history_query_service=history_service,
        )
        g.app_logger = app.logger
        g.op_logger = None

    return app


def _build_real_app(tmp_path, monkeypatch, *, summary_obj) -> Flask:
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
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (3, "priority_first", 1, 1, "partial", json.dumps(summary_obj, ensure_ascii=False), "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()

    from core.services.scheduler.gantt_service import GanttService

    monkeypatch.setattr(
        GanttService,
        "get_week_plan_rows",
        lambda self, **kwargs: {
            "rows": [
                {
                    "日期": "2026-04-13",
                    "批次号": "B001",
                    "图号": "PART-001",
                    "工序": 10,
                    "设备": "MC-01",
                    "人员": "OP-01",
                    "时段": "08:00-10:00",
                }
            ],
            "version": int(kwargs.get("version") or 3),
            "week_start": "2026-04-13",
            "week_end": "2026-04-19",
        },
    )
    return app


def test_week_plan_route_exposes_selected_summary_display(monkeypatch) -> None:
    summary = {
        "warnings": ["告警一"],
        "errors_sample": ["错误一"],
        "error_count": 12,
        "degraded_causes": ["resource_pool_degraded"],
        "degradation_events": [
            {
                "code": "resource_pool_degraded",
                "message": "自动分配资源池构建失败，本次排产已降级为不自动分配资源。",
                "count": 1,
            }
        ],
    }
    history_service = _HistoryServiceStub(json.dumps(summary, ensure_ascii=False))
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/week-plan?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected_history"]["version"] == 3
    assert payload["selected_summary"] == summary
    assert payload["selected_summary_display"]["completion_status"] == "partial"
    assert payload["selected_summary_display"]["result_state"] == {
        "raw_status": "partial",
        "outcome_status": "partial",
        "is_simulated": False,
    }
    assert payload["selected_summary_display"]["primary_degradation"]["details"] == ["资源池构建已降级"]
    assert payload["selected_summary_display"]["warning_total"] == 1
    assert payload["selected_summary_display"]["error_total"] == 12
    assert history_service.version_limits == [30]
    assert history_service.version_queries == [3]


def test_week_plan_route_marks_selected_summary_parse_failure(monkeypatch) -> None:
    history_service = _HistoryServiceStub("{broken json")
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/week-plan?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected_summary"] is None
    assert payload["selected_summary_display"]["summary_parse_state"]["parse_failed"] is True


def test_build_summary_display_state_preserves_simulated_raw_status() -> None:
    from web.viewmodels.scheduler_summary_display import build_summary_display_state

    payload = build_summary_display_state(
        {
            "degradation_events": [
                {"code": "resource_pool_degraded", "message": "", "count": 1},
            ],
            "warnings": [],
            "errors": [],
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        },
        result_status="simulated",
    )

    assert payload["completion_status"] == "success"
    assert payload["result_state"] == {
        "raw_status": "simulated",
        "outcome_status": "success",
        "is_simulated": True,
    }
    assert "\u6a21\u62df\u6392\u4ea7" in str((payload["primary_degradation"] or {}).get("message") or "")
    assert "\u672c\u6b21\u6392\u4ea7\u5df2\u6210\u529f" not in str((payload["primary_degradation"] or {}).get("message") or "")


def test_build_summary_display_state_exposes_warning_pipeline_display() -> None:
    from web.viewmodels.scheduler_summary_display import build_summary_display_state

    payload = build_summary_display_state(
        {
            "degraded_causes": ["summary_merge_failed"],
            "degradation_events": [{"code": "summary_merge_failed", "message": "", "count": 1}],
            "algo": {
                "warning_pipeline": {
                    "algo_warning_count": 2,
                    "summary_warning_count": 0,
                    "summary_merge_attempted": True,
                    "summary_merge_failed": True,
                    "summary_merge_error": "summary_warnings_assignment_failed",
                }
            },
        },
        result_status="success",
    )

    assert payload["warning_pipeline_display"] == {
        "source": "warning_pipeline",
        "message": "摘要告警合并已降级。",
        "note": "摘要告警未能完整合并到历史摘要。",
        "summary_merge_failed": True,
        "summary_merge_error": "summary_warnings_assignment_failed",
        "algo_warning_count": 2,
        "summary_warning_count": 0,
    }


def test_build_summary_display_state_keeps_legacy_warning_pipeline_compat() -> None:
    from web.viewmodels.scheduler_summary_display import build_summary_display_state

    payload = build_summary_display_state(
        {
            "degraded_causes": ["summary_merge_failed"],
        },
        result_status="success",
    )

    assert payload["warning_pipeline_display"] == {
        "source": "legacy_degraded_causes",
        "message": "摘要告警合并已降级。",
        "note": "历史摘要未记录 warning pipeline 明细。",
        "summary_merge_failed": True,
        "summary_merge_error": None,
        "algo_warning_count": None,
        "summary_warning_count": None,
    }


def test_week_plan_route_surfaces_missing_history_but_keeps_preview_rows(monkeypatch) -> None:
    history_service = _HistoryServiceStub("{}", missing_versions=[9])
    gantt_service = _GanttServiceStub(
        rows=[
            {
                "日期": "2026-04-13",
                "批次号": "B9001",
                "图号": "PART-9001",
                "工序": 10,
                "设备": "MC-09",
                "人员": "OP-09",
                "时段": "08:00-10:00",
            }
        ]
    )
    app = _build_app(monkeypatch, history_service, gantt_service=gantt_service)
    client = app.test_client()

    response = client.get("/scheduler/week-plan?version=9")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["version"] == 9
    assert payload["selected_history"] is None
    assert payload["selected_summary"] is None
    assert payload["selected_history_resolution"]["requested_version"] == 9
    assert payload["selected_history_resolution"]["history_missing"] is True
    assert "9" in str(payload["selected_history_resolution"]["message"] or "")
    assert len(payload["preview_rows"]) == 1
    assert history_service.version_queries == [9]


def test_week_plan_page_renders_warning_pipeline_guard_html(tmp_path, monkeypatch) -> None:
    summary = {
        "warnings": ["资源池已降级"],
        "degraded_causes": ["summary_merge_failed"],
        "degradation_events": [{"code": "summary_merge_failed", "message": "", "count": 1}],
        "algo": {
            "warning_pipeline": {
                "algo_warning_count": 2,
                "summary_warning_count": 0,
                "summary_merge_attempted": True,
                "summary_merge_failed": True,
                "summary_merge_error": "summary_warnings_assignment_failed",
            }
        },
    }
    app = _build_real_app(tmp_path, monkeypatch, summary_obj=summary)
    client = app.test_client()

    response = client.get("/scheduler/week-plan?week_start=2026-04-13&version=3")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "摘要告警合并状态：已降级" in html
    assert "算法告警：2 条" in html
    assert "摘要告警：0 条" in html
    assert "摘要告警未能完整合并到历史摘要。" in html
    assert "summary_warnings_assignment_failed" not in html
