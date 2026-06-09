"""回归测试：甘特调整草稿的校验/模拟链路——GanttAdjustmentValidationService.validate_draft 对资源重叠、工序先后、停机/日历窗口、交期与备料风险分别给出 blocked/warning/valid 状态且只读不落正式表；create/record/discard 草稿路由与 validate-simulate 路由可用但未接到甘特页，created_by 强制改写为 web。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.services.scheduler.gantt_adjustment_draft_service import GanttAdjustmentDraftService
from core.services.scheduler.gantt_adjustment_validation_service import GanttAdjustmentValidationService
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 5


def _connect(tmp_path: Path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _count(conn, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(1) AS count FROM {table}").fetchone()
    return int(row["count"])


def _snapshot(conn):
    return {
        "schedule": [dict(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id").fetchall()],
        "history": [dict(row) for row in conn.execute("SELECT * FROM ScheduleHistory ORDER BY id").fetchall()],
        "seq": [dict(row) for row in conn.execute("SELECT * FROM ScheduleVersionSeq ORDER BY version").fetchall()],
        "candidate": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidate ORDER BY id").fetchall()],
        "candidate_rows": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateRows ORDER BY id").fetchall()],
        "candidate_selection": [
            dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateSelection ORDER BY id").fetchall()
        ],
    }


def _seed_base(conn, *, ready_status: str = "yes", due_date: str = "2026-05-20") -> None:
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
          ('B1', 'P001', '零件一', 1, '{due_date}', 'normal', '{ready_status}', 'scheduled'),
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


def _draft_with_time_change(
    conn,
    *,
    op_id: int,
    to_start: str,
    to_end: str,
    to_machine_id=None,
    to_operator_id=None,
    base_plan_role: str = "adopted",
) -> str:
    draft_service = GanttAdjustmentDraftService(conn)
    draft = draft_service.create_draft(base_version=VERSION, base_plan_role=base_plan_role, created_by="pytest")
    draft_service.record_time_change(
        draft_id=draft.draft_id,
        op_id=op_id,
        to_start=to_start,
        to_end=to_end,
    )
    if to_machine_id is not None or to_operator_id is not None:
        draft_service.record_resource_change(
            draft_id=draft.draft_id,
            op_id=op_id,
            to_machine_id=to_machine_id,
            to_operator_id=to_operator_id,
        )
    return draft.draft_id


def _insert_candidate(conn, *, key: str, label: str, detail_saved: str = "yes") -> int:
    cur = conn.execute(
        """
        INSERT INTO ScheduleCandidate(
            version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved
        )
        VALUES (?, ?, ?, 'baseline', 'completed', 'no', ?)
        """,
        (VERSION, key, label, detail_saved),
    )
    return int(cur.lastrowid)


def _seed_candidate_roles(conn) -> int:
    adopted_id = _insert_candidate(conn, key="adopted", label="最终采用")
    baseline_id = _insert_candidate(conn, key="baseline", label="原算法最好")
    conn.executemany(
        """
        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES (?, ?, ?, ?)
        """,
        (
            (VERSION, "adopted", adopted_id, "schedule"),
            (VERSION, "baseline_best", baseline_id, "candidate_rows"),
        ),
    )
    conn.execute(
        """
        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status)
        SELECT version, ?, op_id, machine_id, operator_id, start_time, end_time, lock_status
        FROM Schedule
        WHERE version = ?
        """,
        (baseline_id, VERSION),
    )
    conn.commit()
    return baseline_id


def _codes(result):
    return {issue["code"] for issue in result["issues"]}


def test_validate_draft_valid_change_does_not_touch_formal_tables(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
        )
        before = _snapshot(conn)

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "valid"
        assert result["can_apply"] is True
        assert result["issues"] == []
        assert _snapshot(conn) == before
    finally:
        conn.close()


def test_validate_draft_reports_machine_and_operator_overlap(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 10:30:00",
            to_end="2026-05-04 11:30:00",
            to_machine_id="M1",
            to_operator_id="O1",
        )
        before = _snapshot(conn)

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "blocked"
        assert result["can_apply"] is False
        assert {"machine_overlap", "operator_overlap"} <= _codes(result)
        assert "其他工序" in " ".join(issue["message"] for issue in result["issues"])
        assert _snapshot(conn) == before
    finally:
        conn.close()


def test_validate_draft_reports_precedence_violation(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        draft_id = _draft_with_time_change(
            conn,
            op_id=20,
            to_start="2026-05-04 08:30:00",
            to_end="2026-05-04 09:30:00",
        )

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "blocked"
        assert "precedence_violation" in _codes(result)
        assert "前一道" in " ".join(issue["message"] for issue in result["issues"])
    finally:
        conn.close()


def test_validate_draft_reports_calendar_and_downtime_blockers(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        conn.execute(
            """
            INSERT INTO MachineDowntimes(machine_id, start_time, end_time, reason_code, status)
            VALUES ('M2', '2026-05-04 11:30:00', '2026-05-04 12:30:00', 'maintenance', 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO WorkCalendar(date, day_type, shift_hours, allow_normal, allow_urgent)
            VALUES ('2026-05-05', 'holiday', 0, 'no', 'no')
            """
        )
        conn.commit()
        downtime_draft = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
        )
        calendar_draft = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-05 09:00:00",
            to_end="2026-05-05 10:00:00",
        )
        service = GanttAdjustmentValidationService(conn)

        assert "machine_downtime" in _codes(service.validate_draft(draft_id=downtime_draft))
        assert "calendar_unavailable" in _codes(service.validate_draft(draft_id=calendar_draft))
    finally:
        conn.close()


def test_validate_draft_reports_calendar_window_blocker(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        conn.execute(
            """
            INSERT INTO WorkCalendar(date, day_type, shift_start, shift_end, allow_normal, allow_urgent)
            VALUES ('2026-05-04', 'workday', '08:00', '12:00', 'yes', 'yes')
            """
        )
        conn.commit()
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:30:00",
            to_end="2026-05-04 12:30:00",
        )

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "blocked"
        assert "calendar_window" in _codes(result)
        assert "班次时间" in " ".join(issue["message"] for issue in result["issues"])
    finally:
        conn.close()


def test_validate_draft_reports_due_and_material_warnings(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn, ready_status="no", due_date="2026-05-04")
        conn.execute("UPDATE Batches SET due_date = '2026-05-04', ready_status = 'no' WHERE batch_id = 'B2'")
        conn.commit()
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-05 08:00:00",
            to_end="2026-05-05 09:00:00",
        )
        before = _snapshot(conn)

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "warning"
        assert result["can_apply"] is True
        assert {"due_date_risk", "material_not_ready"} <= _codes(result)
        assert _snapshot(conn) == before
    finally:
        conn.close()


def test_validate_draft_reports_missing_material_status(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        conn.execute("UPDATE Batches SET ready_status = NULL WHERE batch_id = 'B2'")
        conn.commit()
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
        )

        result = GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)

        assert result["status"] == "warning"
        assert "material_status_missing" in _codes(result)
    finally:
        conn.close()


def test_validate_draft_requires_original_plan_role_without_adopted_fallback(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        _seed_candidate_roles(conn)
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
            base_plan_role="baseline_best",
        )
        conn.execute("DELETE FROM ScheduleCandidateSelection WHERE version = ? AND role = 'baseline_best'", (VERSION,))
        conn.commit()
        before = _snapshot(conn)

        with pytest.raises(ValidationError, match="所选方案不存在"):
            GanttAdjustmentValidationService(conn).validate_draft(draft_id=draft_id)
        assert _snapshot(conn) == before
    finally:
        conn.close()


def _build_app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "route.db"
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    point_env_at_shared(monkeypatch)
    (tmp_path / "logs").mkdir()
    (tmp_path / "backups").mkdir()
    (tmp_path / "templates_excel").mkdir()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        _seed_base(conn)
        draft_id = _draft_with_time_change(
            conn,
            op_id=30,
            to_start="2026-05-04 11:00:00",
            to_end="2026-05-04 12:00:00",
        )
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    return importlib.import_module("app").create_app(), draft_id


def test_validate_simulate_route_is_callable_but_not_wired_to_gantt_page(tmp_path: Path, monkeypatch) -> None:
    app, draft_id = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post("/scheduler/gantt/adjustments/validate-simulate", json={"draft_id": draft_id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "valid"

    for rel in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "validate-simulate" not in text
        assert "data-adjustment-url" not in text


def test_adjustment_draft_routes_create_record_and_discard_without_formal_writes(tmp_path: Path, monkeypatch) -> None:
    app, _seeded_draft_id = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    before_conn = get_connection(str(tmp_path / "route.db"))
    try:
        before = _snapshot(before_conn)
    finally:
        before_conn.close()

    create_resp = client.post(
        "/scheduler/gantt/adjustments/create-draft",
        json={
            "base_version": VERSION,
            "base_plan_role": "adopted",
            "created_by": "mallory",
            "reason": "测试草稿",
        },
    )
    create_payload = create_resp.get_json()
    assert create_resp.status_code == 200
    assert create_payload["success"] is True
    draft_id = create_payload["data"]["draft_id"]
    assert create_payload["data"]["created_by"] == "web"

    time_resp = client.post(
        "/scheduler/gantt/adjustments/record-time-change",
        json={
            "draft_id": draft_id,
            "schedule_id": 90,
            "op_id": 30,
            "to_start": "2026-05-04 11:00:00",
            "to_end": "2026-05-04 12:00:00",
        },
    )
    assert time_resp.status_code == 200
    assert time_resp.get_json()["data"]["change_type"] == "move_time"

    resource_resp = client.post(
        "/scheduler/gantt/adjustments/record-resource-change",
        json={
            "draft_id": draft_id,
            "schedule_id": 90,
            "op_id": 30,
            "from_machine_id": "M2",
            "to_machine_id": "M1",
            "from_operator_id": "O2",
            "to_operator_id": "O1",
        },
    )
    assert resource_resp.status_code == 200
    assert resource_resp.get_json()["data"]["change_type"] == "change_resource"

    discard_resp = client.post(
        "/scheduler/gantt/adjustments/discard-draft",
        json={"draft_id": draft_id, "reason": "不采用"},
    )
    assert discard_resp.status_code == 200
    assert discard_resp.get_json()["data"]["status"] == "discarded"

    after_conn = get_connection(str(tmp_path / "route.db"))
    try:
        assert _snapshot(after_conn) == before
        draft = after_conn.execute(
            "SELECT created_by, status, change_count FROM ScheduleAdjustmentDraft WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        assert dict(draft) == {"created_by": "web", "status": "discarded", "change_count": 2}
    finally:
        after_conn.close()
