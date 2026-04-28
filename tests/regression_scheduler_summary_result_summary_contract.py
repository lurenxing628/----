from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.algorithms.evaluation import ScheduleMetrics
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.run.schedule_persistence import build_validated_schedule_payload, persist_schedule
from core.services.scheduler.schedule_summary import build_result_summary
from core.services.scheduler.schedule_summary_types import SummaryBuildContext
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from data.repositories.schedule_repo import ScheduleRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
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
        simulate=True,
        t0=0.0,
    )
    return cfg, batch, result, summary, ctx


def _prepare_db(tmp_path, monkeypatch) -> Path:
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
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    return test_db


def _persist_summary_roundtrip(test_db: Path) -> dict[str, Any]:
    conn = get_connection(str(test_db))
    try:
        op_id = _seed_minimal_scheduler_rows(conn)
        cfg, batch, result, summary, ctx = _build_summary_for_op(op_id=op_id)
        svc = _SummaryAndPersistenceSvc(conn)
        _overdue, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary(svc, ctx=ctx)
        payload = build_validated_schedule_payload([result], allowed_op_ids={int(op_id)})

        persist_schedule(
            svc,
            cfg=cfg,
            version=3,
            validated_schedule_payload=payload,
            summary=summary,
            used_strategy=ctx.used_strategy,
            used_params=ctx.used_params,
            batches={"B001": batch},
            reschedulable_operations=[],
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


def test_result_summary_roundtrip_keeps_public_attempts_and_diagnostics_separate(tmp_path, monkeypatch) -> None:
    test_db = _prepare_db(tmp_path, monkeypatch)

    loaded = _persist_summary_roundtrip(test_db)

    public_attempts = (loaded.get("algo") or {}).get("attempts") or []
    assert public_attempts
    assert all(attempt.get("source") != "candidate_rejected" for attempt in public_attempts)
    assert all("source" not in attempt for attempt in public_attempts)
    assert all(attempt.get("dispatch_mode") == "sgs" for attempt in public_attempts)
    assert all("tag" not in attempt for attempt in public_attempts)
    assert all("used_params" not in attempt for attempt in public_attempts)
    assert all("algo_stats" not in attempt for attempt in public_attempts)
    assert all("origin" not in attempt for attempt in public_attempts)

    diagnostic_attempts = (((loaded.get("diagnostics") or {}).get("optimizer") or {}).get("attempts") or [])
    rejected = [attempt for attempt in diagnostic_attempts if attempt.get("source") == "candidate_rejected"]
    assert rejected[0]["origin"] == {
        "type": "ValidationError",
        "field": "resource",
        "message": INTERNAL_SECRET,
    }
    assert "score" not in rejected[0]


def test_optimizer_diagnostics_secret_is_not_rendered_on_public_scheduler_surfaces(tmp_path, monkeypatch) -> None:
    test_db = _prepare_db(tmp_path, monkeypatch)
    loaded = _persist_summary_roundtrip(test_db)
    assert INTERNAL_SECRET in json.dumps(loaded.get("diagnostics"), ensure_ascii=False)

    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    for path in (
        "/scheduler/analysis?version=3",
        "/system/history?version=3",
        "/scheduler/",
        "/scheduler/week-plan?version=3",
        "/scheduler/gantt?version=3",
        "/scheduler/gantt/data?include_history=1",
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
        "/reports/",
        "/reports/overdue?version=3",
        "/reports/utilization?version=3",
        "/reports/downtime?version=3",
    ):
        response = client.get(path)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, f"{path} 返回异常：{response.status_code}\n{html[:500]}"
        assert INTERNAL_SECRET not in html, path
