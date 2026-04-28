from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from core.services.scheduler.config_service import ConfigService
from web.viewmodels.scheduler_summary_display import build_summary_display_state

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


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
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

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
    import web.routes.scheduler_batches as route_mod

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


def test_scheduler_batches_route_reuses_shared_degraded_display_builder() -> None:
    route_source = _read("web/routes/domains/scheduler/scheduler_batches.py")
    batches_viewmodel_source = _read("web/viewmodels/scheduler_batches_page.py")
    config_route_source = _read("web/routes/domains/scheduler/scheduler_config.py")
    display_state_source = _read("web/routes/domains/scheduler/scheduler_config_display_state.py")

    assert "scheduler_config_display_state" in route_source
    assert "build_scheduler_batches_config_panel_state" in route_source
    assert "build_scheduler_batches_page_view_model" in route_source
    assert "build_summary_display_state" in batches_viewmodel_source
    assert "get_scheduler_visible_config_field_metadata" in display_state_source
    assert "_parse_result_summary_payload_with_meta" in route_source
    assert "latest_summary_display" in batches_viewmodel_source
    assert "latest_other_degradation_messages" in batches_viewmodel_source
    assert 'page_metadata_for(["enforce_ready_default"])' not in route_source
    assert "scheduler_config_display_state" in config_route_source
    assert 'preset_display_state.get("current_config_state")' in config_route_source
    assert "get_scheduler_visible_config_field_metadata" in config_route_source
    assert "SCHEDULER_VISIBLE_CONFIG_FIELDS" in display_state_source
    assert "config_field_warnings" in display_state_source
    assert "config_degraded_fields" in display_state_source
    assert "config_hidden_warnings" in display_state_source
    assert "current_config_state" in batches_viewmodel_source
    assert "runtime_config_state" not in route_source


def test_scheduler_batches_template_surfaces_field_level_degraded_warning() -> None:
    template_source = _read("templates/scheduler/batches.html")
    v2_template_source = _read("web_new_test/templates/scheduler/batches.html")

    assert "scheduler-config-degraded-summary" in template_source
    assert "scheduler-current-config-summary" in template_source
    assert "current_config_state.status_label" in template_source
    assert "current_config_state.repair_notices" in template_source
    assert "config_hidden_warnings" in template_source
    assert "latest_summary_display.primary_degradation" in template_source
    assert "latest_summary_display.summary_parse_state.parse_failed" in template_source
    assert "latest_summary_display.error_total" in template_source
    assert "scheduler-run-degraded-summary" in template_source
    assert "scheduler-run-other-degradation-summary" in template_source
    assert "latest_other_degradation_messages" in template_source
    assert "最近一次排产快照" in template_source
    assert "latest_objective_label" in template_source
    assert "latest_summary_display.result_status_label" in template_source
    assert "status_zh.get(latest_history.result_status" not in template_source
    assert "scheduler-config-degraded-summary" in v2_template_source
    assert "scheduler-current-config-summary" in v2_template_source
    assert "current_config_state.status_label" in v2_template_source
    assert "current_config_state.repair_notices" in v2_template_source
    assert "config_hidden_warnings" in v2_template_source
    assert "latest_summary_display.primary_degradation" in v2_template_source
    assert "latest_summary_display.summary_parse_state.parse_failed" in v2_template_source
    assert "latest_summary_display.error_total" in v2_template_source
    assert "scheduler-run-degraded-summary" in v2_template_source
    assert "scheduler-run-other-degradation-summary" in v2_template_source
    assert "latest_other_degradation_messages" in v2_template_source
    assert "最近一次排产快照" in v2_template_source
    assert "latest_objective_label" in v2_template_source
    assert "latest_summary_display.result_status_label" in v2_template_source
    assert "status_zh.get(latest_history.result_status" not in v2_template_source


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
    assert display["primary_degradation"]["details"] == ["\u8d44\u6e90\u6c60\u6784\u5efa\u5df2\u964d\u7ea7\uff082\uff09"]
    assert list(display.get("display_secondary_degradation_messages") or []) == []


def test_scheduler_analysis_template_uses_shared_objective_label_helper() -> None:
    template_source = _read("templates/scheduler/analysis.html")

    assert "objective_label_for(" not in template_source
    assert "algo_objective_label" in template_source
    assert "best_score_schema_display" in template_source
    assert "algo_config_snapshot_objective_label" in template_source
    assert "selected_history_resolution.message" in template_source
    assert "freeze_display.degradation_reason" not in template_source
    assert "selected_summary_display.display_secondary_degradation_messages" in template_source
    assert "display_summary_degradation_messages" not in template_source


def test_scheduler_week_plan_and_history_templates_surface_secondary_degradation_messages() -> None:
    week_plan_source = _read("templates/scheduler/week_plan.html")
    history_source = _read("templates/system/history.html")

    assert "selected_history_resolution.message" in week_plan_source
    assert "selected_summary_display.display_secondary_degradation_messages" in week_plan_source
    assert "selected_summary_display.display_secondary_degradation_messages" in history_source
    assert "r.result_summary_display.display_secondary_degradation_messages" in history_source


def test_scheduler_batches_templates_render_final_secondary_labels_without_template_side_count_suffix() -> None:
    template_source = _read("templates/scheduler/batches.html")
    v2_template_source = _read("web_new_test/templates/scheduler/batches.html")

    assert "{% if item.count and item.count > 1 %}" not in template_source
    assert "{% if item.count and item.count > 1 %}" not in v2_template_source


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
    assert "当前运行配置缺少基线记录，无法确认与任何方案的一致性；请显式保存或重新应用方案。" in body
    assert "当前配置存在可见兼容修补：" in body
    assert "当前还有内部配置项存在兼容修补：" in body
    assert "自动分配结果回写" in body
    assert "auto_assign_persist" not in body
