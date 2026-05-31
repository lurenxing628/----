from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

from core.infrastructure.database import ensure_schema, get_connection
from tests.resource_dispatch_frontend_support import (
    RESOURCE_DISPATCH_TEMPLATE,
    UI_CONTRACT_CSS,
    read_resource_dispatch_script_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    db_path = tmp_path / "aps_execution_feedback_routes.db"
    log_dir = tmp_path / "logs"
    backup_dir = tmp_path / "backups"
    template_dir = tmp_path / "templates_excel"
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(template_dir))

    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        _seed_execution_feedback_context(conn)
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    app.config["TESTING"] = True
    return app, str(db_path)


def _seed_execution_feedback_context(conn) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name, status)
        VALUES ('T1', '一组', 'active');

        INSERT INTO Machines(machine_id, name, status, team_id)
        VALUES ('M1', '一号设备', 'active', 'T1'), ('M2', '二号设备', 'active', 'T1');

        INSERT INTO Operators(operator_id, name, status, team_id)
        VALUES ('O1', '张三', 'active', 'T1'), ('O2', '李四', 'active', 'T1');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);
        INSERT INTO ScheduleVersionSeq(version) VALUES (2);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
            (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 2),
            (101, 10, 'M1', 'O1', '2026-04-30 08:00:00', '2026-04-30 09:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES
            (1, 'priority_first', 1, 1, 'success', '{}', 'pytest'),
            (2, 'priority_first', 1, 1, 'success', '{}', 'pytest');

        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES
            (2, 'adopted', '正式采用', 'baseline', 'completed', 'no', 'no'),
            (2, 'baseline_best', '原算法代表', 'baseline', 'completed', 'no', 'yes');

        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status)
        VALUES (
            2,
            (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'baseline_best'),
            10,
            'M2',
            'O2',
            '2026-05-01 10:00:00',
            '2026-05-01 11:00:00',
            'unlocked'
        );

        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES
            (2, 'adopted', (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'adopted'), 'schedule'),
            (2, 'baseline_best', (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'baseline_best'), 'candidate_rows');

        INSERT INTO ScheduleAdjustmentDraft(draft_id, base_version, base_plan_role, status, created_by)
        VALUES ('draft-1', 2, 'adopted', 'saved_scenario', 'pytest');

        INSERT INTO ScheduleAdjustmentScenario(
            scenario_id, source_draft_id, base_version, base_plan_role, base_source_table,
            scenario_name, status, validation_status, row_count, created_by
        )
        VALUES ('scenario-plain', 'draft-1', 2, 'adopted', 'schedule', '', 'active', 'valid', 1, 'pytest');

        INSERT INTO ScheduleAdjustmentScenarioRow(
            scenario_id, source_table, source_row_id, op_id, machine_id, operator_id, start_time, end_time, lock_status
        )
        VALUES ('scenario-plain', 'schedule', 100, 10, 'M1', 'O1', '2026-05-01 12:00:00', '2026-05-01 13:00:00', 'unlocked');
        """
    )


def _json(resp) -> Dict[str, Any]:
    return json.loads(resp.get_data(as_text=True) or "{}")


def _event_count(db_path: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents").fetchone()
        return int(row["count"])
    finally:
        conn.close()


def _event_count_for_op(db_path: str, op_id: int) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents WHERE op_id = ?", (op_id,)).fetchone()
        return int(row["count"])
    finally:
        conn.close()


def _events_for_op(db_path: str, op_id: int):
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT event_type, event_time, created_by, quantity_done, quantity_scrapped, reason_code, severity, remark
            FROM OperationExecutionEvents
            WHERE op_id = ?
            ORDER BY id ASC
            """,
            (int(op_id),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _current_card(client) -> Dict[str, Any]:
    resp = client.get(
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    assert resp.status_code == 200
    data = _json(resp)["data"]
    return data["tasks"][0]


def _base_payload(card: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    payload = {
        "version": 2,
        "schedule_id": card["schedule_id"],
        "batch_id": card["batch_id"],
        "requested_plan_role": "adopted",
        "effective_plan_role": "adopted",
        "source_table": "schedule",
        "scenario_id": None,
        "expected_state_revision": card["state_revision"],
        "event_time": "2026-05-01 08:10:00",
        "created_by": "张三",
        "idempotency_key": "route-key-start",
        "operator_id": "O1",
        "machine_id": "M1",
        "remark": "开始加工",
    }
    payload.update(overrides)
    return payload


def _post_controlled(client, url: str, payload: Dict[str, Any]):
    return client.post(url, json=payload, headers={"X-APS-Test-Execution-Feedback": "allow"})


def _current_query() -> str:
    return "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
