"""回归测试：build_result_summary 产出的 result_summary 须把公开 attempts 与内部 diagnostics 分离——公开 attempts 剔除 source/tag/used_params/algo_stats/origin，candidate_rejected 与内部 secret 仅留在 diagnostics 且不渲染到任何 /scheduler 与 /reports 公开页面；并验证缺资源面板仅按 validator 的 scheduled_op_ids 过滤、自动派工/工时不合法等失败不误判为缺资源、完整 errors 与 missing_internal_resource_ops 字段口径正确。"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from core.algorithms.evaluation import ScheduleMetrics
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.run.schedule_persistence import build_validated_schedule_payload, persist_schedule
from core.services.scheduler.summary.schedule_summary import build_result_summary
from core.services.scheduler.summary.schedule_summary_types import SummaryBuildContext
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from data.repositories.schedule_repo import ScheduleRepository
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
INTERNAL_SECRET = "INTERNAL_OPTIMIZER_SECRET"


class _SummaryAndPersistenceSvc:
    logger = None
    op_logger = None

    def __init__(self, conn):
        self.tx_manager = TransactionManager(conn)
        self.history_repo = ScheduleHistoryRepository(conn)
        self.schedule_repo = ScheduleRepository(conn)

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_text(value: Any):
        text = "" if value is None else str(value).strip()
        return text or None


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=1.0,
        enforce_ready_default="yes",
        prefer_primary_skill="yes",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        auto_assign_enabled="no",
        auto_assign_persist="no",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="improve",
        time_budget_seconds=5,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def _seed_minimal_scheduler_rows(conn) -> int:
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P001", "测试零件"))
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity, due_date, status) VALUES (?, ?, ?, ?, ?)", ("B001", "P001", 1, "2026-04-02", "pending"))
    conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC1", "测试设备", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP1", "测试人员", "active"))
    cur = conn.execute(
        """
        INSERT INTO BatchOperations
        (op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("OP-B001-001", "B001", 1, "车削", "internal", "MC1", "OP1", "pending"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _build_summary_for_op(*, op_id: int):
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    cfg = _cfg()
    batch = SimpleNamespace(batch_id="B001", due_date="2026-04-02", status="pending")
    result = SimpleNamespace(
        op_id=int(op_id),
        batch_id="B001",
        machine_id="MC1",
        operator_id="OP1",
        start_time=start,
        end_time=end,
        source="internal",
    )
    summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])
    metrics = ScheduleMetrics(
        overdue_count=0,
        total_tardiness_hours=0.0,
        makespan_hours=2.0,
        changeover_count=0,
        weighted_tardiness_hours=0.0,
    )
    ctx = SummaryBuildContext(
        cfg=cfg,
        version=3,
        normalized_batch_ids=["B001"],
        start_dt=start,
        end_date=None,
        batches={"B001": batch},
        operations=[],
        results=[result],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=(0.0,),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[
            {
                "tag": "start:priority_first|sgs:slack",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "used_params": {"internal_weight": 1},
                "score": [0.0],
                "failed_ops": 0,
                "metrics": {"overdue_count": 0},
                "algo_stats": {"debug": INTERNAL_SECRET},
            },
            {
                "source": "candidate_rejected",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "origin": {
                    "type": "ValidationError",
                    "field": "resource",
                    "message": INTERNAL_SECRET,
                },
            },
        ],
        improvement_trace=[],
        frozen_op_ids=set(),
        readiness_gate_enabled=True,
        simulate=True,
        t0=0.0,
    )
    return cfg, batch, result, summary, ctx


def _prepare_db(tmp_path, monkeypatch) -> Path:
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
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    return test_db


def _persist_summary_roundtrip(test_db: Path) -> Dict[str, Any]:
    conn = get_connection(str(test_db))
    try:
        op_id = _seed_minimal_scheduler_rows(conn)
        cfg, batch, result, summary, ctx = _build_summary_for_op(op_id=op_id)
        svc = _SummaryAndPersistenceSvc(conn)
        _overdue, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary(svc, ctx=ctx)
        payload = build_validated_schedule_payload([result], allowed_op_ids={int(op_id)})

        reschedulable_operations = [SimpleNamespace(id=int(op_id), source="internal")]
        persist_schedule(
            svc,
            cfg=cfg,
            version=3,
            validated_schedule_payload=payload,
            summary=summary,
            used_strategy=ctx.used_strategy,
            used_params=ctx.used_params,
            batches={"B001": batch},
            reschedulable_operations=reschedulable_operations,
            normalized_batch_ids=["B001"],
            created_by="pytest",
            simulate=True,
            frozen_op_ids=set(),
            result_status=result_status,
            result_summary_json=result_summary_json,
            result_summary_obj=result_summary_obj,
            missing_internal_resource_op_ids=set(),
            overdue_items=[],
            time_cost_ms=time_cost_ms,
        )

        row = ScheduleHistoryRepository(conn).get_by_version(3)
        assert row is not None
        return json.loads(row.result_summary or "{}")
    finally:
        conn.close()


def test_result_summary_keeps_full_errors_and_missing_resource_details() -> None:
    op_id = 101
    _cfg_obj, _batch, _result, _summary, ctx = _build_summary_for_op(op_id=op_id)
    errors = [
        f"自制工序未补全设备或人员，无法排产：工序 B001_{idx:02d}"
        for idx in range(1, 13)
    ]
    missing_op = SimpleNamespace(
        id=op_id,
        batch_id="B001",
        seq=5,
        op_code="OP-B001-005",
        op_type_name="车削",
        machine_id="",
        operator_id=None,
    )
    summary = SimpleNamespace(success=False, total_ops=12, scheduled_ops=0, failed_ops=12, warnings=[], errors=errors)
    ctx = replace(
        ctx,
        operations=[missing_op],
        results=[],
        summary=summary,
        missing_internal_resource_op_ids={op_id},
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["error_count"] == 12
    assert result_summary_obj["errors"] == errors
    assert result_summary_obj["errors_sample"] == errors[:10]
    assert "public_error_details" in result_summary_obj
    assert result_summary_obj["errors"] == [item["message"] for item in result_summary_obj["public_error_details"]]
    assert result_summary_obj["missing_internal_resource_count"] == 1
    assert result_summary_obj["missing_internal_resource_ops"] == [
        {
            "op_id": op_id,
            "batch_id": "B001",
            "op_code": "OP-B001-005",
            "seq": 5,
            "op_type_name": "车削",
            "missing_fields": ["设备", "人员"],
        }
    ]


def test_result_summary_does_not_mark_auto_assigned_success_as_missing_resource() -> None:
    op_id = 102
    cfg, batch, _result, _summary, ctx = _build_summary_for_op(op_id=op_id)
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 10, 0, 0)
    missing_original_op = SimpleNamespace(
        id=op_id,
        batch_id="B001",
        seq=5,
        op_code="OP-B001-005",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    auto_assigned_result = SimpleNamespace(
        op_id=op_id,
        batch_id="B001",
        machine_id="MC1",
        operator_id="OP1",
        start_time=start,
        end_time=end,
        source="internal",
    )
    summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])
    ctx = replace(
        ctx,
        # 旧调用路径仍可只依赖 raw results；主路径会传入 validator scheduled_op_ids。
        # 这里显式保持 None，验证兼容 fallback 不破坏自动补资源成功提示。
        scheduled_op_ids=None,
        cfg=cfg,
        batches={"B001": batch},
        operations=[missing_original_op],
        results=[auto_assigned_result],
        summary=summary,
        missing_internal_resource_op_ids={op_id},
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["error_count"] == 0
    assert result_summary_obj["missing_internal_resource_count"] == 0
    assert result_summary_obj["missing_internal_resource_ops"] == []


def test_missing_resource_filter_uses_validated_scheduled_op_ids_not_raw_results() -> None:
    _cfg_obj, _batch, raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    missing_op_101 = SimpleNamespace(
        id=101,
        batch_id="B001",
        seq=1,
        op_code="OP-B001-001",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    missing_op_102 = SimpleNamespace(
        id=102,
        batch_id="B001",
        seq=2,
        op_code="OP-B001-002",
        op_type_name="铣削",
        machine_id="",
        operator_id="",
    )
    summary = SimpleNamespace(success=True, total_ops=2, scheduled_ops=1, failed_ops=1, warnings=[], errors=[])
    ctx = replace(
        ctx,
        operations=[missing_op_101, missing_op_102],
        results=[raw_result_101],
        summary=summary,
        missing_internal_resource_op_ids={101, 102},
        scheduled_op_ids={102},
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["missing_internal_resource_count"] == 1
    assert {item["op_id"] for item in result_summary_obj["missing_internal_resource_ops"]} == {101}


def test_missing_resource_filter_respects_empty_validated_scheduled_ids() -> None:
    _cfg_obj, _batch, raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    missing_op_101 = SimpleNamespace(
        id=101,
        batch_id="B001",
        seq=1,
        op_code="OP-B001-001",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    summary = SimpleNamespace(success=False, total_ops=1, scheduled_ops=0, failed_ops=1, warnings=[], errors=[])
    ctx = replace(
        ctx,
        operations=[missing_op_101],
        results=[raw_result_101],
        summary=summary,
        missing_internal_resource_op_ids={101},
        scheduled_op_ids=set(),
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["missing_internal_resource_count"] == 1
    assert {item["op_id"] for item in result_summary_obj["missing_internal_resource_ops"]} == {101}


@pytest.mark.parametrize(
    "error_message",
    [
        "自制工序缺少自动派工所需工种信息，无法自动分配：工序 OP-B001-001",
        "自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP-B001-001",
        "自动派工没有找到可用的设备和人员组合：工序 OP-B001-001。请检查设备工种、人员可操作设备和资源可用时间后再排产。",
        "工时不合法：工序 OP-B001-001",
    ],
)
def test_auto_assign_failure_does_not_render_as_missing_resource_panel(error_message: str) -> None:
    _cfg_obj, _batch, _raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    missing_op_101 = SimpleNamespace(
        id=101,
        batch_id="B001",
        seq=1,
        op_code="OP-B001-001",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    summary = SimpleNamespace(
        success=False,
        total_ops=1,
        scheduled_ops=0,
        failed_ops=1,
        warnings=[],
        errors=[error_message],
    )
    ctx = replace(
        ctx,
        operations=[missing_op_101],
        results=[],
        summary=summary,
        missing_internal_resource_op_ids={101},
        scheduled_op_ids=set(),
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["errors"] == [error_message]
    assert result_summary_obj["missing_internal_resource_count"] == 0
    assert result_summary_obj["missing_internal_resource_ops"] == []


def test_auto_assign_failure_filter_matches_full_op_code_with_spaces() -> None:
    _cfg_obj, _batch, _raw_result_101, _summary, ctx = _build_summary_for_op(op_id=101)
    op = SimpleNamespace(
        id=101,
        batch_id="B001",
        seq=1,
        op_code="OP SPACE 001",
        op_type_name="车削",
        machine_id="",
        operator_id="",
    )
    summary = SimpleNamespace(
        success=False,
        total_ops=1,
        scheduled_ops=0,
        failed_ops=1,
        warnings=[],
        errors=["工时不合法：工序 OP SPACE 001"],
    )
    ctx = replace(
        ctx,
        operations=[op],
        results=[],
        summary=summary,
        missing_internal_resource_op_ids={101},
        scheduled_op_ids=set(),
    )
    svc = SimpleNamespace(
        _format_dt=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
        _normalize_text=lambda value: str(value).strip() if value else None,
    )

    _overdue, _result_status, result_summary_obj, _result_summary_json, _time_cost_ms = build_result_summary(svc, ctx=ctx)

    assert result_summary_obj["errors"] == ["工时不合法：工序 OP SPACE 001"]
    assert result_summary_obj["missing_internal_resource_count"] == 0
    assert result_summary_obj["missing_internal_resource_ops"] == []
