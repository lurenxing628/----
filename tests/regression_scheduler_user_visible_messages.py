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
from core.shared.field_labels import display_field_label
from web.routes.domains.scheduler import scheduler_config as scheduler_config_route
from web.routes.domains.scheduler.scheduler_user_messages import scheduler_user_visible_app_error_message
from web.viewmodels.scheduler_run_view_result import build_run_schedule_view_result
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
    assert any("排序策略：部分选项填得不对，本次先按默认值处理。" in item for item in result.warnings), result.warnings
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
    assert any("优先级权重：部分数字填得不对，本次先按默认值处理。" in item for item in result.warnings), result.warnings
    assert "BAD_PRIORITY_SECRET" not in str(result.warnings)
    assert "优先级权重" in str(result.warnings)
    assert "priority_weight" not in str(result.warnings)


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


def test_execution_feedback_fields_have_user_visible_labels() -> None:
    expected = {
        "created_by": "反馈人",
        "reason_code": "原因",
        "severity": "严重程度",
        "impact_minutes": "预计影响时间",
        "expected_state_revision": "页面状态",
        "event_time": "反馈时间",
        "idempotency_key": "重复提交标记",
        "quantity_done": "完成数量",
        "quantity_scrapped": "报废数量",
        "affected_machine_id": "影响设备",
        "affected_operator_id": "影响人员",
        "handling_status": "处理状态",
        "suggest_reschedule": "是否建议重新排程",
        "remark": "情况说明",
        "requested_plan_role": "当前方案",
        "effective_plan_role": "实际使用的方案",
        "schedule_id": "排程记录",
        "schedule_version": "排程版本",
        "source_table": "计划来源",
        "scenario_id": "模拟预览",
        "op_id": "工序编号",
        "plan_role": "方案",
    }

    for field, label in expected.items():
        assert display_field_label(field) == label


def test_scheduler_version_validation_message_is_user_facing_chinese(tmp_path, monkeypatch) -> None:
    from core.services.scheduler.version_resolution import VERSION_ERROR_MESSAGE

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    analysis_resp = client.get("/scheduler/analysis?version=abc")
    analysis_html = analysis_resp.get_data(as_text=True)
    assert analysis_resp.status_code == 400
    assert VERSION_ERROR_MESSAGE in analysis_html
    assert "version 不合法" not in analysis_html
    assert "期望整数" not in analysis_html

    gantt_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=0")
    gantt_payload = gantt_resp.get_json()
    assert gantt_resp.status_code == 400
    assert gantt_payload["error"]["message"] == VERSION_ERROR_MESSAGE
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


@pytest.mark.parametrize(
    "field",
    ["batch_ids", "end_date", "start_dt", "批次", "排产", "排产版本", "齐套"],
)
def test_scheduler_direct_validation_fields_keep_user_visible_message(field: str) -> None:
    exc = ValidationError("组合模板资料缺失，请先补齐模板后再排产。", field=field)

    assert scheduler_user_visible_app_error_message(exc) == "组合模板资料缺失，请先补齐模板后再排产。"


@pytest.mark.parametrize("field", ["template", "ext_group_id"])
def test_scheduler_template_validation_fields_do_not_echo_raw_message_without_public_detail(field: str) -> None:
    exc = ValidationError("SECRET_TOKEN /tmp/private.db raw SQL", field=field)

    visible = scheduler_user_visible_app_error_message(exc)

    assert "SECRET_TOKEN" not in visible
    assert "/tmp/private.db" not in visible
    assert "raw SQL" not in visible
    assert "填写不正确，请检查后重试" in visible


@pytest.mark.parametrize("field", ["template", "ext_group_id"])
def test_scheduler_template_validation_fields_accept_explicit_public_user_message(field: str) -> None:
    exc = ValidationError("internal detail SECRET_TOKEN", field=field)
    exc.details = dict(exc.details or {})
    exc.details["user_message"] = "外协工序资料不完整，已停止排产。请检查零件工艺后重试。"

    assert scheduler_user_visible_app_error_message(exc) == "外协工序资料不完整，已停止排产。请检查零件工艺后重试。"


@pytest.mark.parametrize(
    ("result_status", "scheduled_ops", "failed_ops", "headline_category", "headline_prefix", "degradation_message"),
    [
        (
            "success",
            3,
            0,
            "success",
            "排产完成",
            "本次排产已成功，但有些数据或设置需要复核，系统先按能确认的内容继续。",
        ),
        (
            "partial",
            2,
            1,
            "warning",
            "排产部分完成",
            "本次排产部分完成，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
        ),
        (
            "failed",
            0,
            3,
            "error",
            "排产失败",
            "本次排产失败，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
        ),
    ],
)
def test_scheduler_run_degradation_messages_are_user_visible_and_sanitized(
    result_status: str,
    scheduled_ops: int,
    failed_ops: int,
    headline_category: str,
    headline_prefix: str,
    degradation_message: str,
) -> None:
    summary = {
        "completion_status": result_status,
        "total_ops": 3,
        "scheduled_ops": scheduled_ops,
        "failed_ops": failed_ops,
        "degradation_events": [
            {
                "code": "unknown_debug_degradation",
                "message": "sqlite OperationalError raw_internal_error code=E_SECRET /tmp/private.db",
                "scope": "scheduler.internal_scope",
                "field": "secret_token",
                "sample": "SECRET_TOKEN=abc123",
                "count": 1,
            }
        ],
    }
    if result_status == "failed":
        summary.update(
            {
                "error_count": 1,
                "errors_sample": ["Traceback sqlite raw_internal_error code=E_SECRET /tmp/private.db"],
            }
        )

    view_result = build_run_schedule_view_result(
        {
            "version": 8,
            "result_status": result_status,
            "summary": summary,
            "overdue_batches": [],
        }
    )

    secondary_messages = [
        str(item.get("message") or item.get("label") or "")
        for item in list(view_result.secondary_degradation_messages or [])
        if isinstance(item, dict)
    ]
    visible_messages = [
        view_result.headline_message,
        view_result.primary_degradation_message or "",
        *(view_result.error_preview or ()),
        *secondary_messages,
    ]
    visible_text = "\n".join(visible_messages)

    assert view_result.headline_category == headline_category
    assert view_result.headline_message.startswith(f"{headline_prefix}（版本 8）"), view_result.headline_message
    assert view_result.primary_degradation_message is not None
    assert degradation_message in view_result.primary_degradation_message
    assert "排产摘要里有需要注意的提示" in view_result.primary_degradation_message
    if result_status == "failed":
        assert view_result.error_preview == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert "unknown_debug_degradation" not in visible_text
    assert "raw_internal_error" not in visible_text
    assert "E_SECRET" not in visible_text
    assert "/tmp/private.db" not in visible_text
    assert "SECRET_TOKEN" not in visible_text
    assert "scheduler.internal_scope" not in visible_text


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
    assert resource_pool.get("degradation_reason") == "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
    assert downtime_avoid.get("degradation_reason") == "停机区间加载失败，本次排产先不使用停机约束。"
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
            "message": "排产摘要里有需要注意的提示。",
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
            "message": "扩展功能设置读取失败，当前按默认开关运行。",
            "count": 3,
        }
    ]


def test_summary_display_secondary_degradation_does_not_promote_raw_message_after_dedupe() -> None:
    primary_degradation = {
        "details": ["资源池资料不完整"],
        "detail_keys": [("resource_pool_degraded", "资源池资料不完整", 1)],
    }
    secondary = [
        {
            "code": "resource_pool_degraded",
            "label": "资源池资料不完整",
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

    assert display["primary_degradation"]["details"] == ["排产摘要里有需要注意的提示"]
    assert display["secondary_degradation_messages"][0]["message"] == "排产摘要里有需要注意的提示。"
    assert display["errors_preview"] == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert "sqlite" not in str(display["primary_degradation"])
    assert "/tmp/private.db" not in str(display["secondary_degradation_messages"])
    assert "password leaked" not in str(display["errors_preview"])


def test_public_error_details_are_preferred_over_raw_errors() -> None:
    display = build_summary_display_state(
        {
            "error_count": 1,
            "errors": ["排产执行遇到问题，请联系管理员查看日志。"],
            "public_error_details": [
                {
                    "code": "missing_internal_resource",
                    "message": "自制工序未补全设备或人员，无法排产：工序 B001_05",
                }
            ],
        },
        result_status="failed",
    )

    assert display["errors_display"] == ["自制工序未补全设备或人员，无法排产：工序 B001_05"]


def test_malicious_public_error_details_are_generic() -> None:
    display = build_summary_display_state(
        {
            "error_count": 1,
            "public_error_details": [
                {
                    "schema_version": "1.0",
                    "code": "missing_internal_resource",
                    "message": "Traceback sqlite database password leaked /home/app/secret.py",
                }
            ],
        },
        result_status="failed",
    )

    assert display["errors_display"] == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert display["errors_preview"] == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert display["error_display_count"] == 1


@pytest.mark.parametrize(
    "raw",
    [
        "自制工序未补全设备或人员，无法排产：工序 B001_05\nTraceback ...",
        "自制工序未补全设备或人员，无法排产：工序 B001_05 /home/app/service.py",
        "自制工序未补全设备或人员，无法排产：工序 B001_05 File \"x.py\", line 1",
        "自制工序未补全设备或人员，无法排产：工序 B001_05 apikey=abc",
    ],
)
def test_legacy_error_with_sensitive_tail_is_generic(raw: str) -> None:
    display = build_summary_display_state(
        {
            "error_count": 1,
            "errors": [raw],
            "counts": {"op_count": 1, "scheduled_ops": 0, "failed_ops": 1},
        },
        result_status="failed",
    )

    assert display["errors_display"] == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert "Traceback" not in str(display["errors_display"])
    assert "apikey" not in str(display["errors_display"])
    assert "/home/app" not in str(display["errors_display"])


def test_schedule_summary_raw_internal_error_is_not_saved_in_public_errors() -> None:
    from core.models.scheduler_public_errors import build_public_error_records

    records = build_public_error_records(
        [
            "工时不合法：工序 OP001 工时字段不合法：setup_hours='abc'",
            "工时不合法：工序 OP SPACE 001",
            "工时不合法：工序 OP SPACE 002 工时字段不合法：setup_hours='abc'",
            "工时不合法：工序 OP002 Traceback sqlite database password leaked /Users/private/aps.db",
            "外协周期不合法：工序 OP003 ext_days='bad'",
        ]
    )

    messages = [item["message"] for item in records]
    assert messages == [
        "工时不合法：工序 OP001",
        "工时不合法：工序 OP SPACE 001",
        "工时不合法：工序 OP SPACE 002",
        "排产执行遇到问题，请联系管理员查看日志。",
        "外协周期不合法：工序 OP003",
    ]
    assert "setup_hours" not in str(records)
    assert "ext_days" not in str(records)
    assert "/Users/private" not in str(records)


def test_sgs_auto_assign_errors_keep_public_details() -> None:
    from core.models.scheduler_public_errors import build_public_error_records

    records = build_public_error_records(
        [
            "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件）缺少自动派工所需工种信息，请补齐工种或固定设备后再排产。",
            "批次 B-1 的工序 OP-11（顺序 2，工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
            "批次 B-1 的工序 OP-12（顺序 3，工种 数车，图号 P-1，零件 测试件）工时不合法，请修正工时后再排产。",
            "批次 B-1 的工序 OP-13（顺序 4，工种 数车，图号 P-1，零件 测试件）没有找到可用的自动分配设备和人员组合，请检查设备工种、人员可操作设备和资源可用时间后再排产。",
        ]
    )

    assert [item["code"] for item in records] == [
        "auto_assign_inputs_missing",
        "auto_assign_resource_pool_incomplete",
        "invalid_internal_work_hours",
        "auto_assign_no_resource_combination",
    ]
    assert "联系管理员" not in str(records)
    assert all(str(item["message"]).startswith("批次 B-1 的工序 OP-") for item in records)


def test_sgs_missing_resource_error_keeps_public_details() -> None:
    from core.models.scheduler_public_errors import build_public_error_records

    message = "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件，件号 Piece-1）缺少设备、人员，请到批次详情补齐后再排产。"
    dirty_message = "批次 B-1 的工序 OP-11（顺序 2，工种 数车，图号 P-1，零件 Traceback /tmp/private.db）缺少设备，请到批次详情补齐后再排产。"

    records = build_public_error_records([message, dirty_message])

    assert records[0]["code"] == "missing_internal_resource"
    assert records[0]["message"] == message
    assert records[1]["message"] == "排产执行遇到问题，请联系管理员查看日志。"
    assert "Traceback" not in str(records)
    assert "/tmp/private.db" not in str(records)


def test_sgs_auto_assign_public_code_uses_error_suffix_not_context_keywords() -> None:
    from core.models.scheduler_public_errors import build_public_error_records

    records = build_public_error_records(
        [
            "批次 B-1 的工序 OP-12（顺序 3，工种 自动派工资料不完整，图号 P-1，零件 测试件）工时不合法，请修正工时后再排产。",
        ]
    )

    assert [item["code"] for item in records] == ["invalid_internal_work_hours"]


def test_summary_display_keeps_known_scheduler_errors_actionable() -> None:
    display = build_summary_display_state(
        {
            "errors_sample": [
                "自制工序未补全设备或人员，无法排产：工序 UX-0510-E01_05",
                "自动派工资料不完整，本次无法自动补齐设备和人员：工序 UX-0510-E01_06",
                "自动派工没有找到可用的设备和人员组合：工序 UX-0510-E01_07。请检查设备工种、人员可操作设备和资源可用时间后再排产。",
                "排产窗口截止到 2026-05-12：自制工序 OP-10（批次 B-1）预计完工 2026-05-13 10:00 超出窗口",
                "工序 OP001 排产异常：database password leaked",
            ],
            "error_count": 5,
            "counts": {"op_count": 5, "scheduled_ops": 1, "failed_ops": 4},
        },
        result_status="partial",
    )

    assert display["errors_preview"] == [
        "自制工序未补全设备或人员，无法排产：工序 UX-0510-E01_05",
        "自动派工资料不完整，本次无法自动补齐设备和人员：工序 UX-0510-E01_06",
        "自动派工没有找到可用的设备和人员组合：工序 UX-0510-E01_07。请检查设备工种、人员可操作设备和资源可用时间后再排产。",
    ]
    assert "password leaked" not in str(display["errors_preview"])


def test_summary_display_keeps_full_error_detail_list_for_history_pages() -> None:
    errors = [
        f"排产窗口截止到 2026-05-12：自制工序 OP-{idx:02d}（批次 B-{idx}）预计完工 2026-05-13 10:00 超出窗口"
        for idx in range(1, 6)
    ]

    display = build_summary_display_state(
        {
            "errors": errors,
            "errors_sample": errors[:3],
            "error_count": len(errors),
            "counts": {"op_count": 5, "scheduled_ops": 0, "failed_ops": 5},
        },
        result_status="failed",
    )

    assert display["errors_preview"] == errors[:3]
    assert display["errors_display"] == errors
    assert display["error_hidden_count"] == 0


def test_summary_display_known_error_prefix_still_hides_sensitive_tail() -> None:
    display = build_summary_display_state(
        {
            "errors": [
                "工时不合法：工序 OP001 Traceback sqlite database password leaked /Users/private/aps.db",
                "外协周期不合法：工序 OP002 SECRET_TOKEN=abc123",
            ],
            "error_count": 2,
            "counts": {"op_count": 2, "scheduled_ops": 0, "failed_ops": 2},
        },
        result_status="failed",
    )

    assert display["errors_display"] == ["排产执行遇到问题，请联系管理员查看日志。"]
    assert "Traceback" not in str(display["errors_display"])
    assert "password" not in str(display["errors_display"])
    assert "SECRET_TOKEN" not in str(display["errors_display"])
    assert "/Users/private" not in str(display["errors_display"])


def test_summary_display_formats_missing_internal_resource_ops() -> None:
    display = build_summary_display_state(
        {
            "missing_internal_resource_count": 2,
            "missing_internal_resource_ops": [
                {
                    "op_id": 101,
                    "batch_id": "B-001",
                    "seq": 5,
                    "op_type_name": "车削",
                    "missing_fields": ["设备", "人员"],
                },
                {
                    "op_id": 102,
                    "batch_id": "B-002",
                    "seq": 10,
                    "op_code": "OP-10",
                    "missing_fields": ["人员"],
                },
            ],
        },
        result_status="partial",
    )

    assert display["missing_internal_resource_count"] == 2
    assert display["missing_internal_resource_hidden_count"] == 0
    assert display["missing_internal_resource_ops"][0]["label"] == "B-001 / 工序5 / 车削"
    assert display["missing_internal_resource_ops"][0]["missing_text"] == "设备、人员"
    assert display["missing_internal_resource_ops"][1]["label"] == "B-002 / 工序10 / OP-10"
    assert display["missing_internal_resource_ops"][1]["missing_text"] == "人员"


def test_summary_display_sanitizes_historical_missing_resource_fields() -> None:
    long_batch = "B" + "x" * 120
    display = build_summary_display_state(
        {
            "missing_internal_resource_count": 1,
            "missing_internal_resource_ops": [
                {
                    "op_id": 101,
                    "batch_id": long_batch + "\nSECRET_TOKEN=abc",
                    "seq": 5,
                    "op_code": "OP" + "y" * 120,
                    "op_type_name": "车削\nTraceback hidden",
                    "missing_fields": ["设备", "人员", "数据库密码"],
                }
            ],
        },
        result_status="partial",
    )

    item = display["missing_internal_resource_ops"][0]
    assert len(item["batch_id"]) <= 80
    assert "\n" not in item["batch_id"]
    assert "\n" not in item["op_type_name"]
    assert item["missing_fields"] == ["设备", "人员"]
    assert item["missing_text"] == "设备、人员"
    assert "数据库密码" not in str(item)


def test_summary_display_drops_sensitive_missing_resource_legacy_fields() -> None:
    display = build_summary_display_state(
        {
            "missing_internal_resource_count": 1,
            "missing_internal_resource_ops": [
                {
                    "op_id": 101,
                    "batch_id": "B001 SECRET_TOKEN=abc",
                    "seq": 5,
                    "op_code": "OP001",
                    "op_type_name": "Traceback database password leaked",
                    "missing_fields": ["设备", "人员"],
                }
            ],
        },
        result_status="partial",
    )

    item = display["missing_internal_resource_ops"][0]
    assert item["batch_id"] == ""
    assert item["op_type_name"] == ""
    assert item["op_code"] == "OP001"
    assert item["label"] == "工序5 / OP001"
    assert display["missing_internal_resource_count"] == 1
    assert display["missing_internal_resource_hidden_count"] == 0


def test_summary_display_exposes_truncated_flags() -> None:
    display = build_summary_display_state(
        {
            "errors_truncated": True,
            "missing_internal_resource_ops_truncated": True,
            "summary_truncated": True,
        },
        result_status="partial",
    )

    assert display["errors_truncated"] is True
    assert display["missing_internal_resource_ops_truncated"] is True
    assert display["summary_truncated"] is True


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

    assert display["warning_total"] == 1
    assert display["warnings_preview"] == ["冻结窗口存在跳批风险"]
    assert display["warning_hidden_count"] == 0
    assert display["warning_recorded_total"] == 3
    assert display["maintenance_diagnostic_count"] == 2
    assert "sqlite" not in str(display["warnings_preview"])
    assert "SECRET_TOKEN" not in str(display["warnings_preview"])


def test_summary_display_freeze_secondary_requires_public_allowlist_message() -> None:
    primary_degradation = {
        "details": ["冻结窗口资料不完整"],
        "detail_keys": [("freeze_window_degraded", "冻结窗口资料不完整", 1)],
    }
    secondary = [
        {
            "code": "freeze_window_degraded",
            "label": "冻结窗口资料不完整",
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
    assert freeze_window.get("degradation_reason") == "冻结窗口资料不完整，本次排产未使用冻结窗口。"
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
