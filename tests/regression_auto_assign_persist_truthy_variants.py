from __future__ import annotations

import tempfile
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler import BatchService, ConfigService, ScheduleService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_minimal_schedule_case(conn) -> int:
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
    conn.execute(
        "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        ("OP001", "MC_A1", "high", "yes"),
    )
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations
        (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 0.2, 0.1, "active"),
    )
    conn.commit()

    batch_svc = BatchService(conn, logger=None, op_logger=None)
    batch_svc.create_batch_from_template(batch_id="B001", part_no="P1", quantity=10, priority="normal", ready_status="yes")
    op_row = conn.execute(
        "SELECT id, machine_id, operator_id FROM BatchOperations WHERE batch_id='B001' AND source='internal' ORDER BY id LIMIT 1"
    ).fetchone()
    assert op_row is not None
    assert not (op_row["machine_id"] or op_row["operator_id"])
    return int(op_row["id"])


def _run_schedule(conn) -> None:
    cfg_svc = ConfigService(conn, logger=None, op_logger=None)
    cfg_svc.restore_default()
    cfg_svc.set_auto_assign_enabled("yes")
    sch_svc = ScheduleService(conn, logger=None, op_logger=None)
    sch_svc.run_schedule(batch_ids=["B001"], start_dt="2026-02-01 08:00:00", simulate=False, created_by="reg")


def test_auto_assign_persist_truthy_variant_is_normalized_before_persistence() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="aps_reg_auto_assign_persist_"))
    test_db = tmpdir / "aps_reg_auto_assign_persist.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"))
    conn = get_connection(str(test_db))
    try:
        op_id = _seed_minimal_schedule_case(conn)
        conn.execute(
            "UPDATE ScheduleConfig SET config_value=? WHERE config_key='auto_assign_persist'",
            ("1",),
        )
        conn.commit()

        _run_schedule(conn)

        after = conn.execute("SELECT machine_id, operator_id FROM BatchOperations WHERE id=?", (op_id,)).fetchone()
        assert after is not None
        assert str(after["machine_id"] or "").strip()
        assert str(after["operator_id"] or "").strip()
    finally:
        conn.close()


def test_auto_assign_persist_blank_snapshot_does_not_write_back(monkeypatch) -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="aps_reg_auto_assign_persist_blank_"))
    test_db = tmpdir / "aps_reg_auto_assign_persist_blank.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"))
    conn = get_connection(str(test_db))
    try:
        op_id = _seed_minimal_schedule_case(conn)
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        cfg_svc.set_auto_assign_enabled("yes")

        orig_get_snapshot = ConfigService.get_snapshot

        def _patched_get_snapshot(self, *args, **kwargs):
            snap = orig_get_snapshot(self, *args, **kwargs)
            setattr(snap, "auto_assign_persist", "")
            return snap

        monkeypatch.setattr(ConfigService, "get_snapshot", _patched_get_snapshot)

        sch_svc = ScheduleService(conn, logger=None, op_logger=None)
        sch_svc.run_schedule(batch_ids=["B001"], start_dt="2026-02-01 08:00:00", simulate=False, created_by="reg")

        after = conn.execute("SELECT machine_id, operator_id FROM BatchOperations WHERE id=?", (op_id,)).fetchone()
        assert after is not None
        assert not str(after["machine_id"] or "").strip()
        assert not str(after["operator_id"] or "").strip()
    finally:
        conn.close()
