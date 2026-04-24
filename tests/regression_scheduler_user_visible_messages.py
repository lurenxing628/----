from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.algorithms.sort_strategies import SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_summary import build_result_summary
from web.routes.domains.scheduler import scheduler_config as scheduler_config_route
from web.viewmodels.scheduler_summary_display import (
    build_display_secondary_degradation_messages,
    build_summary_display_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
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
        (7, "greedy", 0, 0, "success", "{}", "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_schedule_params_normalization_warnings_are_user_facing_chinese() -> None:
    result = resolve_schedule_params(
        config={},
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params=None,
        start_dt="not-a-datetime",
        end_date="not-a-date",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},
        strict_mode=False,
    )

    assert result.warnings
    assert any("无法解析" in item for item in result.warnings), result.warnings
    assert all("could not be parsed" not in item for item in result.warnings), result.warnings
    assert all("was normalized" not in item for item in result.warnings), result.warnings


def test_schedule_params_snapshot_degradation_warning_does_not_echo_raw_value() -> None:
    result = resolve_schedule_params(
        config={"sort_strategy": "BAD_MODE_SECRET"},
        strategy=None,
        strategy_params=None,
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},
        strict_mode=False,
    )

    assert result.strategy == SortStrategy.PRIORITY_FIRST
    assert result.warnings
    assert any("配置字段已按兼容值标准化" in item for item in result.warnings), result.warnings
    assert "BAD_MODE_SECRET" not in str(result.warnings)


def test_schedule_params_weighted_override_warning_does_not_echo_raw_value() -> None:
    result = resolve_schedule_params(
        config={},
        strategy=SortStrategy.WEIGHTED,
        strategy_params={"priority_weight": "BAD_PRIORITY_SECRET", "due_weight": "0.5"},
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},
        strict_mode=False,
    )

    assert result.used_params["priority_weight"] == 0.4
    assert result.warnings
    assert any("数值字段已按兼容值标准化" in item for item in result.warnings), result.warnings
    assert "BAD_PRIORITY_SECRET" not in str(result.warnings)
    assert "priority_weight" in str(result.warnings)


def test_scheduler_manual_missing_base_dir_message_is_user_facing_chinese() -> None:
    app = Flask(__name__)

    with app.app_context():
        text, mtime = scheduler_config_route._load_manual_text_and_mtime(None, [])

    assert mtime is None
    assert "运行配置缺失" in text
    assert "Runtime config missing" not in text


def test_schedule_params_validation_message_uses_chinese_field_label() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_params(
            config={},
            strategy=SortStrategy.PRIORITY_FIRST,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode="bad-mode",
            dispatch_rule="slack",
            resource_pool={},
            strict_mode=False,
        )

    message = str(exc_info.value)
    assert "派工方式" in message, message
    assert "dispatch_mode" not in message, message


def test_scheduler_version_validation_message_is_user_facing_chinese(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    analysis_resp = client.get("/scheduler/analysis?version=abc")
    analysis_html = analysis_resp.get_data(as_text=True)
    assert analysis_resp.status_code == 400
    assert "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。" in analysis_html
    assert "version 不合法" not in analysis_html
    assert "期望整数" not in analysis_html

    gantt_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=0")
    gantt_payload = gantt_resp.get_json()
    assert gantt_resp.status_code == 400
    assert gantt_payload["error"]["message"] == "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。"
    assert "期望整数" not in gantt_payload["error"]["message"]


def test_mixed_internal_field_message_is_mapped_to_chinese_field_label(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&offset=abc")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "偏移周数填写不正确，请检查后重试。" in body
    assert "offset 不合法" not in body
    assert ">offset<" not in body

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&offset=abc")
    payload = data_resp.get_json()

    assert data_resp.status_code == 400
    assert payload["error"]["message"] == "偏移周数填写不正确，请检查后重试。"
    assert payload["error"]["details"]["field"] == "偏移周数"
    assert "offset" not in json.dumps(payload["error"], ensure_ascii=False)


def test_error_handler_hides_english_internal_message(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)

    @app.get("/__english_validation_error")
    def _boom():
        raise ValidationError("bad objective", field="objective")

    resp = app.test_client().get("/__english_validation_error")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "bad objective" not in body
    assert "填写不正确，请检查后重试。" in body


def test_scheduler_run_degraded_success_message_is_user_facing_chinese() -> None:
    route_source = (REPO_ROOT / "web/routes/domains/scheduler/scheduler_run.py").read_text(encoding="utf-8")
    presenter_source = (REPO_ROOT / "web/viewmodels/scheduler_degradation_presenter.py").read_text(encoding="utf-8")

    assert "primary_degradation" in route_source
    assert "degraded_success" not in route_source
    assert "本次排产已成功，但存在内部降级/兼容修补。" in presenter_source
    assert "本次排产部分完成，且存在内部降级/兼容修补。" in presenter_source
    assert "本次排产失败，且存在内部降级/兼容修补。" in presenter_source


class _SummaryStubSvc:
    logger = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def test_schedule_summary_seed_result_warning_no_longer_surfaces_degraded_success_story() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "freeze_window_days": 0, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        simulate=False,
        t0=0.0,
        algo_stats={"fallback_counts": {"optimizer_seed_result_invalid_count": 2}, "param_fallbacks": {}},
    )

    warnings = list(result_summary_obj.get("warnings") or [])
    assert not any("seed_results 中有" in item for item in warnings), warnings
    assert not any("有效子集继续计算" in item for item in warnings), warnings


def test_schedule_summary_top_level_degraded_causes_include_business_degradations() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "yes", "freeze_window_days": 3, "auto_assign_enabled": "yes"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={"freeze_state": "degraded", "freeze_degradation_reason": "freeze degraded"},
        downtime_meta={"downtime_load_ok": False, "downtime_load_error": "downtime degraded"},
        resource_pool_meta={
            "resource_pool_attempted": True,
            "resource_pool_build_ok": False,
            "resource_pool_build_error": "pool degraded",
        },
        simulate=False,
        t0=0.0,
        warning_merge_status={
            "summary_merge_attempted": True,
            "summary_merge_failed": True,
            "summary_merge_error": "summary.warnings broken: readonly list",
        },
        algo_stats={"fallback_counts": {"optimizer_seed_result_invalid_count": 1}, "param_fallbacks": {}},
    )

    causes = list(result_summary_obj.get("degraded_causes") or [])
    events = list(result_summary_obj.get("degradation_events") or [])
    warning_pipeline = dict((result_summary_obj.get("algo") or {}).get("warning_pipeline") or {})
    resource_pool = dict((result_summary_obj.get("algo") or {}).get("resource_pool") or {})
    downtime_avoid = dict((result_summary_obj.get("algo") or {}).get("downtime_avoid") or {})
    assert result_summary_obj.get("degraded_success") is True
    assert "freeze_window_degraded" in causes, causes
    assert "downtime_avoid_degraded" in causes, causes
    assert "resource_pool_degraded" in causes, causes
    assert "summary_merge_failed" in causes, causes
    assert warning_pipeline.get("summary_merge_error") == "summary_warnings_assignment_failed", warning_pipeline
    assert resource_pool.get("degradation_reason") == "自动分配资源池构建失败，本次排产已降级为不自动分配资源。"
    assert downtime_avoid.get("degradation_reason") == "停机区间加载失败，本次排产已降级为忽略停机约束。"
    summary_merge_event = next(evt for evt in events if str(evt.get("code") or "") == "summary_merge_failed")
    assert "summary.warnings broken" not in str(summary_merge_event.get("message") or ""), summary_merge_event
    assert "pool degraded" not in str(result_summary_obj), result_summary_obj
    assert "downtime degraded" not in str(result_summary_obj), result_summary_obj
    assert "summary.warnings broken" not in str(result_summary_obj), result_summary_obj


def test_schedule_summary_simulated_keeps_run_mode_and_writes_completion_status() -> None:
    summary = SimpleNamespace(
        success=False,
        total_ops=2,
        scheduled_ops=1,
        failed_ops=1,
        warnings=[],
        errors=["部分工序未排程"],
    )

    _overdue, result_status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "no", "freeze_window_days": 0, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={},
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        simulate=True,
        t0=0.0,
    )

    assert result_status == "simulated"
    assert result_summary_obj["is_simulation"] is True
    assert result_summary_obj["completion_status"] == "partial"


def test_public_degradation_events_do_not_expose_raw_internal_fields() -> None:
    from core.models.scheduler_degradation_messages import public_degradation_events

    events = public_degradation_events(
        [
            {
                "code": "unknown_debug_degradation",
                "message": "sqlite OperationalError: /tmp/private.db locked",
                "scope": "scheduler.internal_scope",
                "field": "secret_token",
                "sample": "raw secret sample",
                "count": 2,
            }
        ]
    )

    assert events == [
        {
            "code": "scheduler_degradation",
            "message": "排产摘要存在可见退化。",
            "count": 2,
        }
    ]
    assert "unknown_debug_degradation" not in str(events)
    assert "scheduler.internal_scope" not in str(events)
    assert "secret_token" not in str(events)
    assert "raw secret sample" not in str(events)
    assert "/tmp/private.db" not in str(events)


def test_public_degradation_events_aggregate_by_public_code() -> None:
    from core.models.scheduler_degradation_messages import public_degradation_events

    events = public_degradation_events(
        [
            {"code": "plugin_bootstrap_config_read_failed", "message": "first raw", "count": 1},
            {"code": "plugin_bootstrap_config_read_failed", "message": "second raw", "count": 2},
        ]
    )

    assert events == [
        {
            "code": "plugin_bootstrap_config_read_failed",
            "message": "插件配置读取失败，当前按默认开关运行。",
            "count": 3,
        }
    ]


def test_summary_display_secondary_degradation_does_not_promote_raw_message_after_dedupe() -> None:
    primary_degradation = {
        "details": ["资源池构建已降级"],
        "detail_keys": [("resource_pool_degraded", "资源池构建已降级", 1)],
    }
    secondary = [
        {
            "code": "resource_pool_degraded",
            "label": "资源池构建已降级",
            "message": "Traceback: database connection string leaked",
            "count": 1,
        }
    ]

    display_messages = build_display_secondary_degradation_messages(primary_degradation, secondary)

    assert display_messages == []
    assert "Traceback" not in str(display_messages)
    assert "connection string" not in str(display_messages)


def test_summary_display_unknown_degradation_and_errors_do_not_echo_raw_messages() -> None:
    display = build_summary_display_state(
        {
            "degradation_events": [
                {
                    "code": "unknown_debug_degradation",
                    "message": "sqlite OperationalError: /tmp/private.db locked",
                    "count": 1,
                }
            ],
            "errors_sample": ["工序 OP001 排产异常：database password leaked"],
            "error_count": 1,
            "counts": {"op_count": 1, "scheduled_ops": 0, "failed_ops": 1},
        },
        result_status="partial",
    )

    assert display["primary_degradation"]["details"] == ["排产摘要存在可见退化"]
    assert display["secondary_degradation_messages"][0]["message"] == "排产摘要存在可见退化。"
    assert display["errors_preview"] == ["排程执行出现异常，请查看系统日志。"]
    assert "sqlite" not in str(display["primary_degradation"])
    assert "/tmp/private.db" not in str(display["secondary_degradation_messages"])
    assert "password leaked" not in str(display["errors_preview"])


def test_summary_display_warnings_preview_filters_historical_raw_warnings() -> None:
    display = build_summary_display_state(
        {
            "warnings": [
                "冻结窗口存在跳批风险",
                "sqlite OperationalError: /Users/private/aps.db locked",
                "SECRET_TOKEN=abc123",
            ],
        },
        result_status="success",
    )

    assert display["warning_total"] == 3
    assert display["warnings_preview"] == ["冻结窗口存在跳批风险"]
    assert display["warning_hidden_count"] == 2
    assert "sqlite" not in str(display["warnings_preview"])
    assert "SECRET_TOKEN" not in str(display["warnings_preview"])


def test_summary_display_freeze_secondary_requires_public_allowlist_message() -> None:
    primary_degradation = {
        "details": ["冻结窗口约束已降级"],
        "detail_keys": [("freeze_window_degraded", "冻结窗口约束已降级", 1)],
    }
    secondary = [
        {
            "code": "freeze_window_degraded",
            "label": "冻结窗口约束已降级",
            "message": "冻结窗口处理失败：sqlite OperationalError: /tmp/private.db locked",
            "count": 1,
        }
    ]

    display_messages = build_display_secondary_degradation_messages(primary_degradation, secondary)

    assert display_messages == []
    assert "sqlite" not in str(display_messages)
    assert "/tmp/private.db" not in str(display_messages)


def test_summary_display_warning_pipeline_hides_raw_merge_error() -> None:
    display = build_summary_display_state(
        {
            "degraded_causes": ["summary_merge_failed"],
            "algo": {
                "warning_pipeline": {
                    "summary_merge_failed": True,
                    "summary_merge_error": "sqlite OperationalError: /Users/private/summary.db locked",
                }
            },
        },
        result_status="success",
    )

    warning_pipeline = display["warning_pipeline_display"]
    assert warning_pipeline["summary_merge_error"] == "summary_warnings_assignment_failed"
    assert "sqlite" not in str(warning_pipeline)
    assert "/Users/private" not in str(warning_pipeline)


def test_schedule_summary_freeze_degradation_reason_is_public_message() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "yes", "freeze_window_days": 3, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        freeze_meta={
            "freeze_state": "degraded",
            "freeze_applied": False,
            "freeze_degradation_codes": ["freeze_seed_unavailable"],
            "freeze_degradation_reason": "sqlite OperationalError: /tmp/private.db locked",
        },
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        simulate=False,
        t0=0.0,
    )

    freeze_window = (result_summary_obj.get("algo") or {}).get("freeze_window") or {}
    assert freeze_window.get("degradation_reason") == "冻结窗口约束已降级，本次排产未应用冻结窗口种子。"
    assert "sqlite" not in str(result_summary_obj)
    assert "/tmp/private.db" not in str(result_summary_obj)


def test_schedule_summary_partial_freeze_degradation_reason_does_not_claim_unapplied_seed() -> None:
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=[],
        errors=[],
    )

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        _SummaryStubSvc(),
        cfg={"freeze_window_enabled": "yes", "freeze_window_days": 3, "auto_assign_enabled": "no"},
        version=1,
        normalized_batch_ids=[],
        start_dt=datetime(2026, 4, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=20,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids={1},
        freeze_meta={
            "freeze_state": "degraded",
            "freeze_applied": True,
            "freeze_degradation_codes": ["freeze_seed_unavailable"],
            "freeze_degradation_reason": "sqlite OperationalError: /tmp/private.db locked",
        },
        downtime_meta={"downtime_load_ok": True},
        resource_pool_meta={},
        simulate=False,
        t0=0.0,
    )

    freeze_window = (result_summary_obj.get("algo") or {}).get("freeze_window") or {}
    assert freeze_window.get("freeze_application_status") == "partially_applied", freeze_window
    assert "未应用冻结窗口种子" not in str(freeze_window.get("degradation_reason") or ""), freeze_window
    assert "sqlite" not in str(result_summary_obj)
    assert "/tmp/private.db" not in str(result_summary_obj)
