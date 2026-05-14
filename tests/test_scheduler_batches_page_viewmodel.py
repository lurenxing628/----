from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Tuple

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler.config_service import ConfigService
from web.viewmodels.scheduler_batches_page import (
    ScheduleHistoryDisplayValueError,
    build_batch_rows,
    build_batches_filter_state,
    build_latest_schedule_history_panel_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"

_SCHEMA_TEMPLATE_DIR: Optional[tempfile.TemporaryDirectory] = None
_SCHEMA_TEMPLATE_DB: Optional[Path] = None
_SCHEMA_TEMPLATE_SIGNATURE: Optional[Tuple[int, int]] = None


def _schema_signature() -> Tuple[int, int]:
    stat = SCHEMA_PATH.stat()
    return (int(stat.st_mtime_ns), int(stat.st_size))


def _copy_schema_template(test_db: Path) -> None:
    global _SCHEMA_TEMPLATE_DB
    global _SCHEMA_TEMPLATE_DIR
    global _SCHEMA_TEMPLATE_SIGNATURE

    signature = _schema_signature()
    if (
        _SCHEMA_TEMPLATE_DB is None
        or _SCHEMA_TEMPLATE_SIGNATURE != signature
        or not _SCHEMA_TEMPLATE_DB.exists()
    ):
        if _SCHEMA_TEMPLATE_DIR is not None:
            _SCHEMA_TEMPLATE_DIR.cleanup()
        _SCHEMA_TEMPLATE_DIR = tempfile.TemporaryDirectory(prefix="aps_scheduler_batches_schema_")
        _SCHEMA_TEMPLATE_DB = Path(_SCHEMA_TEMPLATE_DIR.name) / "aps_schema_template.db"
        ensure_schema(str(_SCHEMA_TEMPLATE_DB), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
        _SCHEMA_TEMPLATE_SIGNATURE = signature

    shutil.copyfile(str(_SCHEMA_TEMPLATE_DB), str(test_db))


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

    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)

    _copy_schema_template(test_db)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _with_db(db_path: str):
    return get_connection(db_path)


def _insert_part(conn, part_no: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO Parts (part_no, part_name) VALUES (?, ?)",
        (part_no, f"{part_no} 名称"),
    )


def _insert_batch(
    db_path: str,
    *,
    batch_id: str,
    status: str = "pending",
    ready_status: str = "yes",
    part_no: str = "P001",
) -> None:
    conn = _with_db(db_path)
    try:
        _insert_part(conn, part_no)
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, part_no, 1, "2026-05-01", "urgent", ready_status, status),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_history(
    db_path: str,
    *,
    version: int,
    result_summary: Any,
    result_status: str = "success",
    strategy: str = "priority_first",
) -> None:
    conn = _with_db(db_path)
    try:
        raw_summary = result_summary if isinstance(result_summary, str) else json.dumps(result_summary, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version, strategy, 0, 0, result_status, raw_summary, "pytest"),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_config_keys(db_path: str, keys) -> None:
    conn = _with_db(db_path)
    try:
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        for key in keys:
            conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (str(key),))
        conn.commit()
    finally:
        conn.close()


def _select_markup(body: str, select_id: str) -> str:
    start = body.index(f'<select id="{select_id}"')
    end = body.index("</select>", start)
    return body[start:end]


def _assert_checkbox_before_hidden(body: str, *, field_name: str, checkbox_id: str, hidden_value: str) -> None:
    checkbox_index = body.index(f'id="{checkbox_id}"')
    hidden_index = body.index(f'type="hidden" name="{field_name}" value="{hidden_value}"', checkbox_index)
    assert checkbox_index < hidden_index


def _batch_obj(
    *,
    batch_id: str,
    ready_status: str = "yes",
    status: str = "pending",
    priority: str = "normal",
) -> SimpleNamespace:
    payload = {
        "batch_id": batch_id,
        "part_no": f"P-{batch_id}",
        "quantity": 1,
        "due_date": "2026-05-01",
        "priority": priority,
        "ready_status": ready_status,
        "status": status,
    }
    return SimpleNamespace(**payload, to_dict=lambda: dict(payload))


def _latest_history(*, version: int = 1, strategy: str = "priority_first") -> dict:
    return {
        "version": version,
        "strategy": strategy,
        "result_status": "success",
        "schedule_time": "2026-05-05 10:00:00",
    }


def _valid_metrics() -> dict:
    return {
        "total_tardiness_hours": 0,
        "weighted_tardiness_hours": 0,
        "makespan_hours": 0,
        "changeover_count": 0,
        "machine_util_avg": 0,
    }


def _auto_assign_state(value: Any) -> dict:
    return {"value": str(value or ""), "label": str(value or "-"), "description": ""}


def test_batches_filter_state_preserves_default_and_empty_status_contract() -> None:
    default_state = build_batches_filter_state(has_status_arg=False, raw_status=None, raw_only_ready=None)
    empty_state = build_batches_filter_state(has_status_arg=True, raw_status="", raw_only_ready="partial")

    assert default_state.status == "pending"
    assert default_state.service_status == "pending"
    assert default_state.only_ready == ""
    assert empty_state.status == ""
    assert empty_state.service_status is None
    assert empty_state.only_ready == "partial"


@pytest.mark.parametrize(
    ("only_ready", "expected_batch", "expected_label"),
    (
        ("yes", "B002", "齐套"),
        ("partial", "B001", "部分齐套"),
        ("no", "B003", "未齐套"),
    ),
)
def test_batch_rows_filter_ready_and_add_public_labels(
    only_ready: str,
    expected_batch: str,
    expected_label: str,
) -> None:
    batches = [
        _batch_obj(
            batch_id="B001",
            priority="urgent",
            ready_status="partial",
        ),
        _batch_obj(
            batch_id="B002",
            ready_status="yes",
        ),
        _batch_obj(
            batch_id="B003",
            ready_status="no",
        ),
    ]

    rows = build_batch_rows(
        batches,
        only_ready=only_ready,
        priority_label=lambda value: {"urgent": "急件", "normal": "普通"}.get(value, "-"),
        ready_label=lambda value: {"partial": "部分齐套", "yes": "齐套", "no": "未齐套"}.get(value, "-"),
        batch_status_label=lambda value: {"pending": "待排"}.get(value, "-"),
    )

    assert [row["batch_id"] for row in rows] == [expected_batch]
    assert "priority_zh" not in rows[0]
    assert "ready_status_zh" not in rows[0]
    assert "status_zh" not in rows[0]
    assert rows[0]["ready_status_label"] == expected_label
    assert rows[0]["status_label"] == "待排"


def test_batches_page_defaults_to_pending_status_and_renders_pending_rows(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "B-PENDING" in body
    assert "B-SCHEDULED" not in body
    assert 'value="pending" selected' in body
    assert "js-batch-check" in body
    assert "js-select-all" in body


def test_batches_page_renders_run_option_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="jsRunScheduleForm"' in body
    assert 'id="runEnforceReady"' in body
    assert 'name="enforce_ready"' in body
    assert 'id="runStrictMode"' in body
    assert 'name="strict_mode"' in body
    assert 'type="checkbox"' in body
    assert 'type="hidden" name="enforce_ready" value="no"' in body
    assert 'type="hidden" name="strict_mode" value="no"' in body
    _assert_checkbox_before_hidden(body, field_name="enforce_ready", checkbox_id="runEnforceReady", hidden_value="no")
    _assert_checkbox_before_hidden(body, field_name="strict_mode", checkbox_id="runStrictMode", hidden_value="no")


def test_batches_page_empty_status_lists_all_statuses_without_run_controls(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")

    response = app.test_client().get("/scheduler/?status=")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "B-PENDING" in body
    assert "B-SCHEDULED" in body
    assert "批次列表" in body
    assert "选择批次并执行排产" not in body
    assert '<option value="" selected>（全部）</option>' in _select_markup(body, "schedulerBatchesStatusFilter")
    assert "js-batch-check" not in body
    assert "js-select-all" not in body
    assert "jsSelectedCount" not in body
    assert 'formaction="/scheduler/simulate"' not in body
    assert "排产开始时间" not in body


@pytest.mark.parametrize(
    ("status", "visible_batch", "selected_option"),
    (
        ("scheduled", "B-SCHEDULED", '<option value="scheduled" selected>已排</option>'),
        ("processing", "B-PROCESSING", '<option value="processing" selected>加工中</option>'),
        ("completed", "B-COMPLETED", '<option value="completed" selected>已完成</option>'),
        ("cancelled", "B-CANCELLED", '<option value="cancelled" selected>已取消</option>'),
    ),
)
def test_batches_page_non_pending_status_hides_run_controls(
    tmp_path,
    monkeypatch,
    status: str,
    visible_batch: str,
    selected_option: str,
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")
    _insert_batch(db_path, batch_id="B-PROCESSING", status="processing")
    _insert_batch(db_path, batch_id="B-COMPLETED", status="completed")
    _insert_batch(db_path, batch_id="B-CANCELLED", status="cancelled")

    response = app.test_client().get(f"/scheduler/?status={status}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert visible_batch in body
    assert "B-PENDING" not in body
    assert selected_option in _select_markup(body, "schedulerBatchesStatusFilter")
    assert "js-batch-check" not in body
    assert "js-select-all" not in body
    assert "jsSelectedCount" not in body
    assert 'formaction="/scheduler/simulate"' not in body
    assert "排产开始时间" not in body


@pytest.mark.parametrize(
    ("ready_status", "visible_batch", "visible_label", "hidden_batches"),
    (
        ("yes", "B-READY", "齐套", ("B-PARTIAL", "B-NO")),
        ("partial", "B-PARTIAL", "部分齐套", ("B-READY", "B-NO")),
        ("no", "B-NO", "未齐套", ("B-READY", "B-PARTIAL")),
    ),
)
def test_batches_page_only_ready_filters_visible_rows(
    tmp_path,
    monkeypatch,
    ready_status: str,
    visible_batch: str,
    visible_label: str,
    hidden_batches: tuple[str, str],
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PARTIAL", ready_status="partial")
    _insert_batch(db_path, batch_id="B-READY", ready_status="yes")
    _insert_batch(db_path, batch_id="B-NO", ready_status="no")

    response = app.test_client().get(f"/scheduler/?only_ready={ready_status}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert visible_batch in body
    for hidden_batch in hidden_batches:
        assert hidden_batch not in body
    assert f'value="{ready_status}" selected' in body
    assert visible_label in body


def test_batches_page_empty_filtered_result_uses_filter_specific_message(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "B-SCHEDULED" not in body
    assert "当前筛选条件下暂无批次数据，可以调整状态或齐套条件" in body
    assert "aps-empty-state" in body


def test_batches_page_renders_config_degraded_public_messages(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _delete_config_keys(
        db_path,
        (
            "objective",
            ConfigService.ACTIVE_PRESET_KEY,
            ConfigService.ACTIVE_PRESET_REASON_KEY,
            "auto_assign_persist",
        ),
    )

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "当前配置有 " in body
    assert "个需要复核的修正项" in body
    assert "平时不直接显示的设置需要检查" in body
    assert "自动补设备人员" in body
    assert "保存补齐资源" in body
    assert "查看处理提示" in body
    assert "auto_assign_persist" not in body


def test_batches_page_without_latest_history_renders_empty_history_message(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "aps-empty-state" in body
    assert "还没有排过产" in body
    assert "排产后这里会显示最近一次排产结果。" in body
    assert 'aps-summary-value">v' not in body


def test_batches_page_latest_summary_parse_failed_renders_history_and_warning(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7, result_summary="{invalid json")

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "最近一次排产快照" in body
    assert 'aps-latest-schedule-label">版本' in body
    assert 'aps-latest-schedule-value">v7' in body
    assert "还没有排过产" not in body
    assert "当前版本的排产摘要读取失败，页面仅展示基础历史信息。" in body
    assert "{invalid json" not in body


@pytest.mark.parametrize(
    ("strategy", "mode", "metric_overrides", "raw_value"),
    (
        ("future_strategy", "improve", {}, "future_strategy"),
        ("priority_first", "future_mode", {}, "future_mode"),
        ("priority_first", "improve", {"machine_util_avg": "abc"}, "abc"),
    ),
)
def test_batches_page_degrades_unknown_latest_history_display_value(
    tmp_path,
    monkeypatch,
    strategy: str,
    mode: str,
    metric_overrides: dict,
    raw_value: str,
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    metrics = {**_valid_metrics(), **metric_overrides}
    _insert_history(
        db_path,
        version=9,
        strategy=strategy,
        result_summary={
            "algo": {
                "mode": mode,
                "objective": "min_overdue",
                "metrics": metrics,
            },
            "warnings": [],
            "errors": [],
        },
    )

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "最近一次排产历史摘要不完整，请到系统管理里的排产历史查看这次排产的提醒摘要。" in body
    assert 'aps-latest-schedule-value">v9' in body
    assert "B-PENDING" in body
    assert "jsRunScheduleForm" in body
    assert "jsSelectedCount" in body
    assert "batchesTable" in body
    assert raw_value not in body


@pytest.mark.parametrize(
    ("latest_history", "latest_summary", "message"),
    (
        (
            _latest_history(strategy="future_strategy"),
            None,
            "未知排产策略：future_strategy",
        ),
        (
            _latest_history(),
            {"algo": {"mode": "future_mode", "objective": "min_overdue", "metrics": _valid_metrics()}},
            "未知排产模式：future_mode",
        ),
    ),
)
def test_latest_history_panel_rejects_unknown_display_values(
    latest_history: dict,
    latest_summary: Optional[dict],
    message: str,
) -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match=message):
        build_latest_schedule_history_panel_state(
            latest_history=latest_history,
            latest_summary=latest_summary,
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


@pytest.mark.parametrize(
    ("latest_history", "latest_summary", "message"),
    (
        (
            _latest_history(strategy=""),
            None,
            "排产历史缺少排产策略",
        ),
        (
            _latest_history(),
            {"algo": {"mode": "", "objective": "min_overdue", "metrics": _valid_metrics()}},
            "排产历史摘要缺少排产模式",
        ),
        (
            _latest_history(),
            {
                "algo": {
                    "mode": "improve",
                    "objective": "min_overdue",
                    "metrics": {**_valid_metrics(), "machine_util_avg": "abc"},
                }
            },
            "排产历史摘要 metrics 字段不是数字：machine_util_avg",
        ),
    ),
)
def test_latest_history_panel_rejects_incomplete_display_values(
    latest_history: dict,
    latest_summary: Optional[dict],
    message: str,
) -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match=message):
        build_latest_schedule_history_panel_state(
            latest_history=latest_history,
            latest_summary=latest_summary,
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


@pytest.mark.parametrize(
    ("latest_summary", "message"),
    (
        ({}, "排产历史摘要缺少 algo"),
        ({"algo": []}, "排产历史摘要 algo 字段不是对象"),
    ),
)
def test_latest_history_panel_rejects_missing_or_invalid_algo(latest_summary: dict, message: str) -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match=message):
        build_latest_schedule_history_panel_state(
            latest_history=_latest_history(),
            latest_summary=latest_summary,
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


@pytest.mark.parametrize(
    ("metrics_value", "message"),
    (
        (None, "排产历史摘要 algo 缺少 metrics"),
        ([], "排产历史摘要 algo.metrics 字段不是对象"),
        ("bad", "排产历史摘要 algo.metrics 字段不是对象"),
    ),
)
def test_latest_history_panel_rejects_missing_or_invalid_metrics(metrics_value: Any, message: str) -> None:
    algo = {
        "mode": "improve",
        "objective": "min_overdue",
    }
    if metrics_value is not None:
        algo["metrics"] = metrics_value

    with pytest.raises(ScheduleHistoryDisplayValueError, match=message):
        build_latest_schedule_history_panel_state(
            latest_history=_latest_history(),
            latest_summary={"algo": algo, "warnings": [], "errors": []},
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_batches_page_latest_algo_config_snapshot_renders_public_snapshot_state(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(
        db_path,
        version=8,
        result_summary={
            "algo": {
                "mode": "improve",
                "objective": "min_overdue",
                "metrics": {
                    "total_tardiness_hours": 2,
                    "weighted_tardiness_hours": 3,
                    "makespan_hours": 4,
                    "changeover_count": 1,
                    "machine_util_avg": 0.5,
                },
                "config_snapshot": {"auto_assign_enabled": "no", "auto_assign_persist": "yes"},
            },
            "warnings": [],
            "errors": [],
        },
    )

    response = app.test_client().get("/scheduler/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "最近一次排产快照" in body
    assert 'aps-latest-schedule-label">版本' in body
    assert 'aps-latest-schedule-value">v8' in body
    assert "排产方式" in body
    assert "优先级优先" in body
    assert "自动补设备人员" in body
    assert 'aps-summary-value">已关闭' in body
    assert "保存补齐资源" in body
    assert "查看说明" in body
    assert 'aps-summary-value">已启用' in body


def test_scheduler_batches_route_uses_page_view_model(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")

    route_mod = importlib.import_module("web.routes.domains.scheduler.scheduler_batches")
    original_builder = route_mod.build_scheduler_batches_page_view_model
    calls = []

    class SentinelViewModel:
        def __init__(self, inner):
            self.inner = inner

        def as_template_context(self):
            context = self.inner.as_template_context()
            context["batches"] = [
                {
                    "batch_id": "SENTINEL-FROM-VM",
                    "part_no": "P-VM",
                    "quantity": 1,
                    "due_date": "2026-05-01",
                    "priority_label": "急件",
                    "ready_status_label": "齐套",
                    "status_label": "待排",
                }
            ]
            return context

    def recording_builder(**kwargs):
        calls.append(kwargs)
        return SentinelViewModel(original_builder(**kwargs))

    monkeypatch.setattr(route_mod, "build_scheduler_batches_page_view_model", recording_builder)

    response = app.test_client().get("/scheduler/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert len(calls) == 1
    assert calls[0]["filter_state"].status == "pending"
    assert calls[0]["batches"][0]["batch_id"] == "B-PENDING"
    assert calls[0]["config_panel"].current_config_state
    assert calls[0]["latest_panel"].latest_history is None
    assert "SENTINEL-FROM-VM" in body
    assert "B-PENDING" not in body
