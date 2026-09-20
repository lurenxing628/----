"""Shared scenario data and app fixtures, separate from collected tests."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 5
SCENARIO_ID = "scenario-single-day"
SCENARIO_DRAFT_ID = "draft-single-day"
_SCENARIO_COLUMNS = (
    "scenario_id", "source_draft_id", "base_version", "base_plan_role", "base_source_table",
    "base_candidate_id", "base_candidate_key", "scenario_name", "status", "validation_status",
    "issue_count", "issues_json", "row_count", "execution_snapshot_revision",
    "execution_snapshot_op_ids", "execution_snapshot_op_count", "created_by", "published_version",
    "published_by", "published_reason", "published_at", "created_at", "updated_at",
)


def _connect(tmp_path: Path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))

def _seed_base(conn) -> None:
    conn.executescript(
        f"""
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '设备一', 'active'), ('M2', '设备二', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '人员一', 'active'), ('O2', '人员二', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一'), ('P002', '零件二');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES
          ('B1', 'P001', '零件一', 1, '2026-05-20', 'normal', 'yes', 'scheduled'),
          ('B2', 'P002', '零件二', 1, '2026-05-20', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES
          (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled'),
          (20, 'OP20', 'B1', 'piece-a', 20, '钻孔', 'internal', 'scheduled'),
          (30, 'OP30', 'B2', 'piece-b', 10, '铣削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES ({VERSION});

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
          (70, 10, 'M1', 'O1', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION}),
          (80, 20, 'M1', 'O1', '2026-05-04 10:00:00', '2026-05-04 11:00:00', 'unlocked', {VERSION}),
          (90, 30, 'M2', 'O2', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', {VERSION});

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES ({VERSION}, 'priority_first', 2, 3, 'success', '{{}}', 'pytest');
        """
    )
    conn.commit()


def _saved_scenario(conn) -> ScheduleAdjustmentScenario:
    """Seed the saved scenario the retired draft/scenario services used to write.

    Same rows the retired GanttAdjustmentScenarioService.save_scenario produced for
    the ``_seed_base`` plan: version 5 copied through, op 30 moved to 11:00-12:00.
    """
    conn.execute(
        "INSERT INTO ScheduleAdjustmentScenario(scenario_id, source_draft_id, base_version, base_plan_role, "
        "base_source_table, scenario_name, status, validation_status, issue_count, issues_json, row_count, "
        "execution_snapshot_revision, execution_snapshot_op_ids, execution_snapshot_op_count, created_by) "
        "VALUES (?, ?, ?, 'adopted', 'schedule', '单日模拟', 'active', 'valid', 0, '[]', 3, "
        "'execution-snapshot:pytest', '[10, 20, 30]', 3, 'planner')",
        (SCENARIO_ID, SCENARIO_DRAFT_ID, VERSION),
    )
    conn.executemany(
        "INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id, source_table, source_row_id, op_id, machine_id, "
        "operator_id, start_time, end_time, lock_status, is_changed) "
        "VALUES (?, 'schedule', ?, ?, ?, ?, ?, ?, 'unlocked', ?)",
        [
            (SCENARIO_ID, 70, 10, "M1", "O1", "2026-05-04 08:00:00", "2026-05-04 09:00:00", "no"),
            (SCENARIO_ID, 90, 30, "M2", "O2", "2026-05-04 11:00:00", "2026-05-04 12:00:00", "yes"),
            (SCENARIO_ID, 80, 20, "M1", "O1", "2026-05-04 10:00:00", "2026-05-04 11:00:00", "no"),
        ],
    )
    row = conn.execute(
        "SELECT " + ", ".join(_SCENARIO_COLUMNS) + " FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
        (SCENARIO_ID,),
    ).fetchone()
    conn.commit()
    return ScheduleAdjustmentScenario.from_row(dict(zip(_SCENARIO_COLUMNS, tuple(row))))


def _build_app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "aps.db"
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    point_env_at_shared(monkeypatch)
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "backups").mkdir(exist_ok=True)

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    return importlib.import_module("app").create_app()
