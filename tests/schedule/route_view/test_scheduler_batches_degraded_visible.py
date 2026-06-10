"""回归测试：排产批次页（/scheduler/）的降级信息可见性契约——scheduler_batches 路由复用共享的 build_summary_display_state / scheduler_config_display_state 构建器，模板透出字段级降级提示与"当前配置状态/基线未记录"且不再用旧的 status_zh/strategy_zh 等口径；history 查询异常不被吞、build_summary_display_state 去重主降级并过滤次级降级消息、配置缺 provenance 时只读地标记 degraded。"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, g

from core.services.scheduler.config.config_service import ConfigService
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT
from web.viewmodels.scheduler_summary_display import build_summary_display_state


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _read_analysis_template() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "templates/scheduler/analysis.html",
            "templates/scheduler/analysis_parts/_selected_overview.html",
            "templates/scheduler/analysis_parts/_summary_warnings.html",
        )
    )


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _build_real_app(tmp_path, monkeypatch):
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

    from core.infrastructure.database import ensure_schema

    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)

    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _mutate_scheduler_config(db_path: str, *, delete_keys=()) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        for key in list(delete_keys or []):
            conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (str(key),))
        conn.commit()
    finally:
        conn.close()


class _BatchServiceStub:
    def list(self, status=None):
        return []


class _HistoryServiceStub:
    def list_recent(self, limit=1):
        return []


def _build_batches_app(monkeypatch, config_service: ConfigService) -> Flask:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    import web.routes.domains.scheduler.scheduler_batches as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-batches-readonly"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(
            batch_service=_BatchServiceStub(),
            config_service=config_service,
            schedule_history_query_service=_HistoryServiceStub(),
        )
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_batches_latest_history_query_failure_is_not_swallowed() -> None:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    import web.routes.domains.scheduler.scheduler_batches as route_mod

    class _BrokenHistoryService:
        def list_recent(self, limit=1):
            raise RuntimeError("history query failed")

    with pytest.raises(RuntimeError, match="history query failed"):
        route_mod._load_latest_schedule_history_panel_inputs(_BrokenHistoryService())


def test_build_summary_display_state_exposes_filtered_display_secondary_messages() -> None:
    display = build_summary_display_state(
        {
            "degradation_events": [
                {"code": "freeze_window_degraded", "message": "", "count": 1},
                {"code": "merge_context_degraded", "message": "", "count": 1},
            ],
            "warnings": [],
            "errors": [],
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        },
        result_status="partial",
    )

    assert display["primary_degradation"] is not None
    assert len(list(display["primary_degradation"].get("details") or [])) == 2
    assert [item["code"] for item in display["secondary_degradation_messages"]] == [
        "freeze_window_degraded",
        "merge_context_degraded",
    ]
    assert list(display.get("display_secondary_degradation_messages") or []) == []


def test_build_summary_display_state_dedupes_counted_primary_degradation_from_secondary() -> None:
    display = build_summary_display_state(
        {
            "degradation_events": [
                {"code": "resource_pool_degraded", "message": "", "count": 2},
            ],
            "warnings": [],
            "errors": [],
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        },
        result_status="partial",
    )

    assert display["primary_degradation"] is not None
    assert display["primary_degradation"]["details"] == ["\u8d44\u6e90\u6c60\u8d44\u6599\u4e0d\u5b8c\u6574\uff082\uff09"]
    assert list(display.get("display_secondary_degradation_messages") or []) == []


def test_scheduler_batches_page_keeps_missing_objective_and_provenance_readonly(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        config_service = ConfigService(conn, logger=None, op_logger=None)
        config_service.restore_default()
        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
            ("objective", config_service.ACTIVE_PRESET_KEY, config_service.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()

        app = _build_batches_app(monkeypatch, config_service)
        client = app.test_client()

        first_payload = client.get("/scheduler/").get_json()
        second_payload = client.get("/scheduler/").get_json()

        remaining = {
            row["config_key"]
            for row in conn.execute(
                "SELECT config_key FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
                ("objective", config_service.ACTIVE_PRESET_KEY, config_service.ACTIVE_PRESET_REASON_KEY),
            ).fetchall()
        }
        assert remaining == set(), remaining
        assert first_payload["current_config_state"]["degraded"] is True
        assert first_payload["current_config_state"]["provenance_missing"] is True
        assert first_payload["current_config_state"]["baseline_label"] == "基线未记录"
        assert second_payload["current_config_state"]["degraded"] is True
        assert second_payload["current_config_state"]["provenance_missing"] is True
    finally:
        conn.close()


def test_scheduler_batches_page_renders_provenance_and_hidden_degraded_html(tmp_path, monkeypatch) -> None:
    app, db_path = _build_real_app(tmp_path, monkeypatch)
    _mutate_scheduler_config(
        db_path,
        delete_keys=(
            "objective",
            ConfigService.ACTIVE_PRESET_KEY,
            ConfigService.ACTIVE_PRESET_REASON_KEY,
            "auto_assign_persist",
        ),
    )
    client = app.test_client()

    response = client.get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "当前配置状态" in body
    assert "基线未记录" in body
    assert "auto_assign_persist" not in body
