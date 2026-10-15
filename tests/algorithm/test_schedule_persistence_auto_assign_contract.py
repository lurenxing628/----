"""共同排产 payload 校验与 Schedule 唯一索引迁移合同。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Set

import pytest

from core.errors import ValidationError
from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema
from core.services.scheduler.repository_bundle import build_schedule_repository_bundle
from core.services.scheduler.run.schedule_payload_contract import (
    ValidatedSchedulePayload,
    ValidatedScheduleRow,
    build_validated_schedule_payload,
    validate_payload_before_persist,
)
from tests._support.migration_schema_helpers import load_legacy_migration_schema
from tests._support.paths import REPO_ROOT


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


def _result(
    op_id: int,
    *,
    machine_id: Optional[str] = "MC_A",
    operator_id: Optional[str] = "OP_A",
    source: str = "internal",
    start_offset: int = 0,
    end_offset: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        op_id=op_id,
        op_code=f"B001_{op_id:02d}",
        batch_id="B001",
        seq=op_id,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=_make_dt(start_offset),
        end_time=_make_dt(end_offset),
        source=source,
        op_type_name="A",
    )


def _result_with_raw_op_id(raw_op_id: Any) -> SimpleNamespace:
    return SimpleNamespace(
        op_id=raw_op_id,
        op_code="B001_DIRTY",
        batch_id="B001",
        seq=2,
        machine_id="MC_A",
        operator_id="OP_A",
        start_time=_make_dt(2),
        end_time=_make_dt(3),
        source="internal",
        op_type_name="A",
    )


def _assert_validation_reason(results: List[Any], *, allowed_op_ids: Set[int], reason: str) -> Dict[str, Any]:
    with pytest.raises(ValidationError) as exc_info:
        build_validated_schedule_payload(results, allowed_op_ids=allowed_op_ids)
    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == reason, details
    return details


def test_schedule_payload_error_priority_and_no_actionable_details() -> None:
    invalid = _result(1, start_offset=1, end_offset=1)
    valid = _result(2, start_offset=2, end_offset=3)
    out_of_scope = _result(99, start_offset=3, end_offset=4)

    details = _assert_validation_reason(
        [invalid, valid, out_of_scope],
        allowed_op_ids={1, 2},
        reason="out_of_scope_schedule_rows",
    )
    assert details.get("sample_op_ids") == [99], details
    assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details

    details = _assert_validation_reason(
        [invalid, valid],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )
    assert details.get("invalid_schedule_row_count") == 1, details
    assert "start_time must be earlier than end_time" in "\n".join(details.get("validation_errors") or [])

    details = _assert_validation_reason(
        [_result(1, start_offset=1, end_offset=1), _result(2, start_offset=2, end_offset=2)],
        allowed_op_ids={1, 2},
        reason="no_actionable_schedule_rows",
    )
    assert len(details.get("validation_errors") or []) == 2, details


def test_schedule_payload_rejects_duplicate_op_id_before_persistence() -> None:
    details = _assert_validation_reason(
        [
            _result(1, machine_id="MC_A", start_offset=0, end_offset=1),
            _result(1, machine_id="MC_B", start_offset=2, end_offset=3),
        ],
        allowed_op_ids={1},
        reason="duplicate_schedule_rows",
    )

    assert details.get("sample_op_ids") == [1], details
    assert details.get("count") == 1, details


@pytest.mark.parametrize(
    "invalid_result, expected_text",
    [
        (_result(2, source="internal", machine_id=None, operator_id="OP_A"), "internal 工序必须有设备和人员"),
        (_result(2, source="internal", machine_id="MC_A", operator_id=None), "internal 工序必须有设备和人员"),
        (
            SimpleNamespace(
                op_id=2,
                op_code="B001_02",
                batch_id="B001",
                seq=2,
                machine_id="MC_A",
                operator_id="OP_A",
                start_time="2026-01-01 08:00:00",
                end_time=_make_dt(1),
                source="internal",
                op_type_name="A",
            ),
            "start_time/end_time 必须是有效时间",
        ),
        (_result(2, source="legacy", machine_id="MC_A", operator_id="OP_A"), "source 必须是 internal 或 external"),
    ],
)
def test_schedule_payload_rejects_invalid_persist_rows_before_any_valid_save(invalid_result, expected_text) -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", start_offset=0, end_offset=1)

    details = _assert_validation_reason(
        [valid, invalid_result],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )

    assert expected_text in "\n".join(details.get("validation_errors") or []), details


@pytest.mark.parametrize("raw_op_id", [None, True, False, 1.0, "1.0", 0, "0", "abc"])
def test_schedule_payload_rejects_dirty_result_op_id_without_escaping_validation_error(raw_op_id: Any) -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", start_offset=0, end_offset=1)

    details = _assert_validation_reason(
        [valid, _result_with_raw_op_id(raw_op_id)],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )

    assert "工序编号不合法" in "\n".join(details.get("validation_errors") or []), details


def test_schedule_payload_rejects_result_source_that_disagrees_with_operation_source() -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", source="internal")
    wrong_source = _result(2, machine_id="MC_A", operator_id="OP_A", source="external")
    operations = [
        SimpleNamespace(id=1, source="internal"),
        SimpleNamespace(id=2, source="internal"),
    ]

    with pytest.raises(ValidationError) as exc_info:
        build_validated_schedule_payload(
            [valid, wrong_source],
            allowed_op_ids={1, 2},
            operations=operations,
        )

    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == "invalid_schedule_rows", details
    assert "source 与原工序不一致" in "\n".join(details.get("validation_errors") or []), details


def test_schedule_payload_rejects_dirty_operation_source_instead_of_trusting_result_source() -> None:
    result = _result(1, machine_id="MC_A", operator_id="OP_A", source="internal")
    operations = [SimpleNamespace(id=1, source="legacy")]

    with pytest.raises(ValidationError) as exc_info:
        build_validated_schedule_payload(
            [result],
            allowed_op_ids={1},
            operations=operations,
        )

    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == "invalid_schedule_rows", details
    assert "source 必须是 internal 或 external" in "\n".join(details.get("validation_errors") or []), details


def _seed_common(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "part", "yes"))
    conn.execute(
        """
        INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("B001", "P001", "part", 1, "2026-01-10", "normal", "yes", "pending"),
    )
    for machine_id in ("MC_A", "MC_B", "MC_C", "MC_D", "MC_KEEP"):
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)",
            (machine_id, machine_id, "active"),
        )
    for operator_id in ("OP_A", "OP_B", "OP_C", "OP_D", "OP_KEEP"):
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (operator_id, operator_id, "active"),
        )
    conn.executemany(
        """
        INSERT INTO BatchOperations
        (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                op_id,
                f"B001_{op_id:02d}",
                "B001",
                None,
                op_id,
                "OT_A",
                "A",
                source,
                machine_id,
                operator_id,
                None,
                1.0,
                0.0,
                None,
                "pending",
            )
            for op_id, source, _label, machine_id, operator_id in rows
        ],
    )
    conn.commit()


def test_persist_schedule_revalidates_manual_payload_before_writing() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "ready", "MC_A", "OP_A")])
        svc = build_schedule_repository_bundle(conn)
        operations = [svc.op_repo.get(1)]
        payload = ValidatedSchedulePayload(
            schedule_rows=[
                ValidatedScheduleRow(
                    op_id=1,
                    machine_id="",
                    operator_id="OP_A",
                    start_time=_make_dt(0),
                    end_time=_make_dt(1),
                    source="internal",
                )
            ],
            scheduled_op_ids={1},
            assigned_by_op_id={},
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_payload_before_persist(payload, reschedulable_operations=operations)

        details = dict(getattr(exc_info.value, "details", {}) or {})
        assert details.get("reason") == "invalid_schedule_rows", details
        assert "internal 工序必须有设备和人员" in "\n".join(details.get("validation_errors") or []), details
        assert int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule WHERE version=31").fetchone()["cnt"] or 0) == 0
    finally:
        conn.close()


@pytest.mark.parametrize(
    "payload, operations, expected_text",
    [
        (
            ValidatedSchedulePayload(
                schedule_rows=[
                    ValidatedScheduleRow(
                        op_id=1,
                        machine_id="",
                        operator_id="",
                        start_time=_make_dt(0),
                        end_time=_make_dt(1),
                        source="external",
                    )
                ],
                scheduled_op_ids={1},
                assigned_by_op_id={},
            ),
            [SimpleNamespace(id=1, source="internal")],
            "source 与原工序不一致",
        ),
        (
            ValidatedSchedulePayload(
                schedule_rows=[
                    ValidatedScheduleRow(
                        op_id=1,
                        machine_id="MC_A",
                        operator_id="OP_A",
                        start_time=_make_dt(0),
                        end_time=_make_dt(1),
                        source="internal",
                    )
                ],
                scheduled_op_ids={1},
                assigned_by_op_id={},
            ),
            [],
            "工序超出本次可重排范围",
        ),
        (
            ValidatedSchedulePayload(
                schedule_rows=[
                    ValidatedScheduleRow(
                        op_id=1,
                        machine_id="MC_A",
                        operator_id="OP_A",
                        start_time=_make_dt(0),
                        end_time=_make_dt(1),
                        source="internal",
                    )
                ],
                scheduled_op_ids=[1, 1],  # type: ignore[arg-type]
                assigned_by_op_id={},
            ),
            [SimpleNamespace(id=1, source="internal")],
            "payload.scheduled_op_ids: 重复工序编号 1",
        ),
    ],
)
def test_persist_schedule_revalidates_manual_payload_scope_source_and_ids(payload, operations, expected_text) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "ready", "MC_A", "OP_A")])

        with pytest.raises(ValidationError) as exc_info:
            validate_payload_before_persist(payload, reschedulable_operations=operations)

        details = dict(getattr(exc_info.value, "details", {}) or {})
        assert details.get("reason") == "invalid_schedule_rows", details
        assert expected_text in "\n".join(details.get("validation_errors") or []), details
        assert int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule WHERE version=32").fetchone()["cnt"] or 0) == 0
        assert int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleHistory WHERE version=32").fetchone()["cnt"] or 0) == 0
    finally:
        conn.close()


def test_schedule_schema_rejects_duplicate_version_op_rows() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "missing", None, None)])
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_A", "OP_A", "2026-01-01 08:00:00", "2026-01-01 09:00:00", "unlocked", 21),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 21),
            )
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 22),
        )
    finally:
        conn.close()


def test_schedule_unique_migration_rejects_existing_duplicate_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_duplicate_schedule.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE SchemaVersion (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO SchemaVersion (id, version) VALUES (1, 6);
            CREATE TABLE Schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_id INTEGER NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                version INTEGER DEFAULT 1
            );
            INSERT INTO Schedule (op_id, start_time, end_time, version)
            VALUES (1, '2026-01-01 08:00:00', '2026-01-01 09:00:00', 21);
            INSERT INTO Schedule (op_id, start_time, end_time, version)
            VALUES (1, '2026-01-01 10:00:00', '2026-01-01 11:00:00', 21);
            """
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="重复排程"):
        ensure_schema(str(db_path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)


def test_schedule_unique_migration_creates_index_and_preserves_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v6_schedule_unique.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_legacy_migration_schema(conn, version=6)
        _seed_common(
            conn,
            [
                (1, "internal", "op1", "MC_A", "OP_A"),
                (2, "internal", "op2", "MC_B", "OP_B"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "MC_A", "OP_A", "2026-01-01 08:00:00", "2026-01-01 09:00:00", "unlocked", 31),
                (2, "MC_B", "OP_B", "2026-01-01 09:00:00", "2026-01-01 10:00:00", "unlocked", 31),
                (1, "MC_A", "OP_A", "2026-01-02 08:00:00", "2026-01-02 09:00:00", "unlocked", 32),
            ],
        )
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_schedule_version_op_unique'"
        ).fetchone() is None
        conn.executemany(
            "INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary) "
            "VALUES (?,'priority_first',1,2,'success','{}')", [(31,), (32,)],
        )
        before_rows = [tuple(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id")]
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(backup_dir))

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        version_row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        assert version_row is not None
        assert int(version_row["version"]) == CURRENT_SCHEMA_VERSION

        index_row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='index'
              AND name='idx_schedule_version_op_unique'
              AND tbl_name='Schedule'
            LIMIT 1
            """
        ).fetchone()
        assert index_row is not None

        rows = conn.execute("SELECT op_id, version FROM Schedule ORDER BY version, op_id, id").fetchall()
        assert [(int(row["op_id"]), int(row["version"])) for row in rows] == [
            (1, 31),
            (2, 31),
            (1, 32),
        ]
        assert [tuple(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id")] == before_rows

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "MC_A",
                    "OP_A",
                    "2026-01-03 08:00:00",
                    "2026-01-03 09:00:00",
                    "unlocked",
                    31,
                ),
            )
    finally:
        conn.close()
