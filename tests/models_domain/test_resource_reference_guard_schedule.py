"""设备、人员仓储均识别仅存在于排产表中的引用。"""

from __future__ import annotations

import os

from core.infrastructure.database import ensure_schema, get_connection
from data.repositories.machine_repo import MachineRepository
from data.repositories.operator_repo import OperatorRepository
from tests._support.paths import REPO_ROOT


def _new_conn(tmp_path):
    db_path = tmp_path / "aps_test.db"
    ensure_schema(str(db_path), logger=None, schema_path=os.path.join(str(REPO_ROOT), "schema.sql"))
    return get_connection(str(db_path))


def _insert_part_batch_and_op(conn, *, op_code: str, machine_id=None, operator_id=None) -> int:
    conn.execute("INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)", ("PART-001", "回转壳体", "[]"))
    conn.execute(
        "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("B001", "PART-001", "回转壳体", 5, "2026-03-08", "urgent", "yes", "scheduled"),
    )
    cur = conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (op_code, "B001", "P1", 10, "车削", "internal", machine_id, operator_id, "scheduled"),
    )
    return int(cur.lastrowid)


def test_machine_delete_blocks_schedule_only_reference(tmp_path) -> None:
    conn = _new_conn(tmp_path)
    try:
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status, remark) VALUES (?, ?, ?, ?)",
            ("MC001", "数控车床1", "active", ""),
        )
        op_id = _insert_part_batch_and_op(conn, op_code="OP-B001-10", machine_id=None, operator_id=None)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, "MC001", None, "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
        )
        conn.commit()

        repo = MachineRepository(conn)
        assert repo.is_referenced_by_schedule("MC001") is True
        assert repo.has_any_schedule_machine_reference() is True
    finally:
        conn.close()


def test_operator_replace_blocks_schedule_only_reference(tmp_path) -> None:
    conn = _new_conn(tmp_path)
    try:
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)",
            ("OP001", "张三", "active", ""),
        )
        op_id = _insert_part_batch_and_op(conn, op_code="OP-B001-10", machine_id=None, operator_id=None)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, None, "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
        )
        conn.commit()

        repo = OperatorRepository(conn)
        assert repo.is_referenced_by_schedule("OP001") is True
        assert repo.has_any_schedule_operator_reference() is True
    finally:
        conn.close()
