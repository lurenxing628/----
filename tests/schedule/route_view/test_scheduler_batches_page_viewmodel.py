"""批次过滤、运行表单和公开摘要保持原业务契约；真实服务投影与退役 GET 分开核对，不恢复旧 HTML。"""

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
from werkzeug.datastructures import MultiDict

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler.config.config_service import ConfigService
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT
from tests._support.schedule_retirement import (
    assert_retired_scope,
    capture_schedule_context,
    initialize_read_fixture,
    projection_text,
)
from web.routes.helpers.form_values import form_toggle_bool
from web.viewmodels.scheduler_batches_page import (
    ScheduleHistoryDisplayValueError,
    build_batch_rows,
    build_batches_filter_state,
    build_latest_schedule_history_panel_state,
)

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
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

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
    app = app_mod.create_app()
    initialize_read_fixture(app)
    return app, str(test_db)


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


def _batches_context(app, path="/scheduler/") -> dict:
    """Capture actual retained business inputs, then check the public retirement."""
    client = app.test_client()
    context = capture_schedule_context(
        client, endpoint="scheduler.batches_page", path=path, template="scheduler/batches.html",
    )
    body = assert_retired_scope(client, path, message="没有跳转，也没有丢掉任何条件")
    for retired_control in ("jsRunScheduleForm", "js-batch-check", "js-select-all", "jsSelectedCount"):
        assert retired_control not in body
    return context


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


@pytest.mark.parametrize("status", ("scheduled", "processing", "completed", "cancelled"))
def test_batches_filter_state_preserves_non_pending_status_for_service(status: str) -> None:
    state = build_batches_filter_state(has_status_arg=True, raw_status=status, raw_only_ready=None)

    assert state.status == status
    assert state.service_status == status


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

    context = _batches_context(app)
    assert [row["batch_id"] for row in context["batches"]] == ["B-PENDING"]
    assert context["status"] == "pending"
    assert context["pager"]["total"] == 1
    assert [option.toggle.name for option in context["run_options"]] == ["enforce_ready", "strict_mode"]


def test_batches_page_renders_run_option_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")

    context = _batches_context(app)
    ready, strict = [option.toggle for option in context["run_options"]]
    assert (ready.id, ready.name) == ("runEnforceReady", "enforce_ready")
    assert (strict.id, strict.name) == ("runStrictMode", "strict_mode")
    for toggle in (ready, strict):
        assert toggle.value == "yes" and toggle.hidden_value == "no"
        assert form_toggle_bool(MultiDict([(toggle.name, toggle.value), (toggle.name, toggle.hidden_value)]), toggle.name)
        assert not form_toggle_bool(MultiDict([(toggle.name, toggle.hidden_value)]), toggle.name)


def test_batches_page_empty_status_lists_all_statuses_without_run_controls(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")

    context = _batches_context(app, "/scheduler/?status=")
    assert {row["batch_id"] for row in context["batches"]} == {"B-PENDING", "B-SCHEDULED"}
    assert context["status"] == ""
    assert context["pager"]["total"] == 2


def test_batches_page_non_pending_status_hides_run_controls(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")
    _insert_batch(db_path, batch_id="B-PROCESSING", status="processing")
    _insert_batch(db_path, batch_id="B-COMPLETED", status="completed")
    _insert_batch(db_path, batch_id="B-CANCELLED", status="cancelled")

    context = _batches_context(app, "/scheduler/?status=scheduled")
    assert [row["batch_id"] for row in context["batches"]] == ["B-SCHEDULED"]
    assert context["status"] == "scheduled"
    assert context["batches"][0]["status_label"] == "已排"
    assert context["pager"]["total"] == 1


def test_batches_page_only_ready_filter_connects_to_visible_rows(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PARTIAL", ready_status="partial")
    _insert_batch(db_path, batch_id="B-READY", ready_status="yes")
    _insert_batch(db_path, batch_id="B-NO", ready_status="no")

    context = _batches_context(app, "/scheduler/?only_ready=yes")
    assert [row["batch_id"] for row in context["batches"]] == ["B-READY"]
    assert context["only_ready"] == "yes"
    assert context["batches"][0]["ready_status_label"] == "齐套"
    assert context["pager"]["total"] == 1


def test_batches_page_empty_filtered_result_uses_filter_specific_message(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-SCHEDULED", status="scheduled")

    context = _batches_context(app)
    assert context["batches"] == []
    assert context["status"] == "pending"
    assert context["only_ready"] == ""
    assert context["pager"]["total"] == 0


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

    context = _batches_context(app)
    body = projection_text(context["config_notice_items"], context["current_config_display_items"])
    assert context["current_config_state"]["degraded"] is True
    assert "当前配置有 " in body
    assert "个需要复核的修正项" in body
    assert "平时不直接显示的设置需要检查" in body
    assert "自动补设备人员" in body
    assert "保存补齐资源" in body
    assert "查看处理提示" in body
    assert "auto_assign_persist" not in body


def test_batches_page_without_latest_history_renders_empty_history_message(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)

    context = _batches_context(app)
    assert context["latest_history"] is None
    assert context["latest_summary"] is None
    assert context["latest_head_items"] == ()
    assert context["latest_metric_items"] == ()
    assert context["latest_metrics"] is None


def test_batches_page_latest_summary_parse_failed_renders_history_and_warning(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_history(db_path, version=7, result_summary="{invalid json")

    context = _batches_context(app)
    body = projection_text(context["latest_head_items"], context["latest_notice_items"])
    assert context["latest_history"]["version"] == 7
    assert context["latest_summary"] is None
    assert context["latest_summary_display"]["summary_parse_state"]["parse_failed"] is True
    assert "版本" in body and "v7" in body
    assert "当前版本的排产摘要读取失败，页面仅展示基础历史信息。" in body
    assert "{invalid json" not in body


def test_batches_page_degrades_unknown_latest_history_display_value(
    tmp_path,
    monkeypatch,
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    metrics = {**_valid_metrics(), "machine_util_avg": "abc"}
    _insert_history(
        db_path,
        version=9,
        strategy="priority_first",
        result_summary={
            "algo": {
                "mode": "improve",
                "objective": "min_overdue",
                "metrics": metrics,
            },
            "warnings": [],
            "errors": [],
        },
    )

    context = _batches_context(app)
    body = projection_text(context["latest_head_items"], context["latest_notice_items"])
    assert "最近一次排产历史摘要不完整，请到系统管理里的排产历史查看这次排产的提醒摘要。" in body
    assert context["latest_history"]["version"] == 9 and "v9" in body
    assert context["latest_metrics"] is None and context["latest_metric_items"] == ()
    assert [row["batch_id"] for row in context["batches"]] == ["B-PENDING"]
    assert [option.toggle.name for option in context["run_options"]] == ["enforce_ready", "strict_mode"]
    assert "abc" not in body


def test_batches_page_degrades_unknown_latest_history_strategy_without_raw_value(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_batch(db_path, batch_id="B-PENDING", status="pending")
    _insert_history(
        db_path,
        version=10,
        strategy="future_strategy",
        result_summary={
            "algo": {
                "mode": "improve",
                "objective": "min_overdue",
                "metrics": _valid_metrics(),
            },
            "warnings": [],
            "errors": [],
        },
    )

    context = _batches_context(app)
    body = projection_text(context["latest_head_items"], context["latest_notice_items"], context["latest_meta_items"])
    assert "最近一次排产历史摘要不完整，请到系统管理里的排产历史查看这次排产的提醒摘要。" in body
    assert context["latest_history"]["version"] == 10 and "v10" in body
    assert context["latest_strategy_label"] == "-"
    assert [row["batch_id"] for row in context["batches"]] == ["B-PENDING"]
    assert "future_strategy" not in body


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

    context = _batches_context(app)
    items = {item.label: item.value for item in context["latest_meta_items"]}
    assert context["latest_history"]["version"] == 8
    assert "v8" in projection_text(context["latest_head_items"])
    assert items["自动补设备人员"] == "已关闭"
    assert context["latest_auto_assign_persist_state"]["label"] == "已启用"


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

    context = _batches_context(app)

    assert len(calls) == 1
    assert calls[0]["filter_state"].status == "pending"
    assert calls[0]["batches"][0]["batch_id"] == "B-PENDING"
    assert calls[0]["config_panel"].current_config_state
    assert calls[0]["latest_panel"].latest_history is None
    assert [row["batch_id"] for row in context["batches"]] == ["SENTINEL-FROM-VM"]
