"""回归测试：超期报表页 /reports/overdue 及其导出（含模拟方案预览 scenario_id 入参）把延期诊断以大白话中文呈现（查看为什么晚了/建议先复核/证据等级/证据缺口/下一步），不下结论式归因（不出现"物料不够导致延期"），且不向用户泄露 trace_meta、rule_version、source_table、scenario_id、根因 等内部术语；导出"诊断依据"sheet 表头固定为七列。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from tests._support.paths import REPO_ROOT

TESTS_ROOT = REPO_ROOT / "tests"
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from core.services.report.report_engine import ReportEngine  # noqa: E402
from tests._support.excel_templates import point_env_at_shared  # noqa: E402
from tests.scheduler_analysis.test_scheduler_delay_diagnosis_contract import (  # noqa: E402
    VERSION,
    _seed_base,
    _seed_candidates,
    _seed_scenario,
)


def _build_app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "aps.db"
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    point_env_at_shared(monkeypatch)
    ensure_schema(str(db_path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        _seed_base(conn)
        _seed_candidates(conn)
        scenario_id = _seed_scenario(conn)
        conn.commit()
    finally:
        conn.close()

    for name in ("app", "web.routes.reports", "web.routes.report_plan_preview"):
        sys.modules.pop(name, None)
    import app as app_mod  # noqa: E402

    return app_mod.create_app(), scenario_id


def _insert_bad_due_date_batch() -> None:
    db_path = Path(os.environ["APS_DB_PATH"])
    conn = get_connection(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES ('B_BAD_DUE', 'P001', '坏交期批次', 1, '坏交期', 'normal', 'yes', 'scheduled')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _insert_mixed_finish_time_batch() -> None:
    db_path = Path(os.environ["APS_DB_PATH"])
    conn = get_connection(str(db_path))
    try:
        conn.executescript(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES ('B_MIXED_FINISH', 'P001', '混合时间批次', 1, '2026-06-02', 'normal', 'yes', 'scheduled');

            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (70, 'OP-MIX-10', 'B_MIXED_FINISH', 'piece-mix-1', 10, '车削', 'internal', 'scheduled');

            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (71, 'OP-MIX-20', 'B_MIXED_FINISH', 'piece-mix-2', 20, '磨削', 'internal', 'scheduled');

            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (170, 70, 'M1', 'O1', '2026/06/01 08:00', '2026/06/01 12:00', 'unlocked', 11);

            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (171, 71, 'M1', 'O1', '2026-06-03 08:00', '2026-06-03 10:00', 'unlocked', 11);
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_overdue_engine_surfaces_bad_due_date_as_data_issue(tmp_path: Path, monkeypatch) -> None:
    _build_app(tmp_path, monkeypatch)
    _insert_bad_due_date_batch()
    db_path = Path(os.environ["APS_DB_PATH"])
    conn = get_connection(str(db_path))
    try:
        report = ReportEngine(conn).overdue_batches(VERSION, plan_role="adopted")
    finally:
        conn.close()

    by_batch = {str(item.get("batch_id")): item for item in report["items"]}
    bad_due = by_batch["B_BAD_DUE"]
    assert bad_due["bucket"] == "due_date_invalid"
    assert bad_due["bucket_label"] == "交期写法异常"
    assert "交期写法不对" in bad_due["data_issue_message"]
    assert report["report_invalid_due_count"] == 1
    assert "交期写法不对" in report["report_degradation_message"]


def test_overdue_finish_time_uses_parsed_time_order_not_raw_text(tmp_path: Path, monkeypatch) -> None:
    _build_app(tmp_path, monkeypatch)
    _insert_mixed_finish_time_batch()
    db_path = Path(os.environ["APS_DB_PATH"])
    conn = get_connection(str(db_path))
    try:
        report = ReportEngine(conn).overdue_batches(VERSION, plan_role="adopted")
    finally:
        conn.close()

    by_batch = {str(item.get("batch_id")): item for item in report["items"]}
    mixed = by_batch["B_MIXED_FINISH"]
    assert mixed["bucket"] == "scheduled_overdue"
    assert mixed["finish_time"] == "2026-06-03 10:00:00"
    assert float(mixed["delay_hours"]) == 10.0


