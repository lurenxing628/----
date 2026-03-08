from __future__ import annotations

import os
import sqlite3
import tempfile
from typing import Callable

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema
from core.infrastructure.migrations.v1 import run as run_v1
from core.infrastructure.migrations.v2 import run as run_v2
from core.infrastructure.migrations.v3 import run as run_v3
from core.infrastructure.migrations.v4 import run as run_v4
from core.infrastructure.migrations.v5 import run as run_v5

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "schema.sql")


class _BrokenLogger:
    def __init__(self) -> None:
        self.calls = []

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.calls.append(("warning", str(msg)))
        raise RuntimeError("logger.warning exploded")

    def error(self, msg: str, *args, **kwargs) -> None:
        self.calls.append(("error", str(msg)))
        raise RuntimeError("logger.error exploded")

    def info(self, msg: str, *args, **kwargs) -> None:
        self.calls.append(("info", str(msg)))
        raise RuntimeError("logger.info exploded")


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.infos = []

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.warnings.append(str(msg))

    def info(self, msg: str, *args, **kwargs) -> None:
        self.infos.append(str(msg))

    def error(self, msg: str, *args, **kwargs) -> None:
        self.warnings.append(str(msg))


def _load_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    return conn


def _prep_v1(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)", ("P1", "零件", "", "no"))
    conn.execute(
        "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, ready_date, status, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("B1", "P1", "零件", 1, "2026/3/1", "invalid", "pending", "normal"),
    )
    conn.commit()


def _prep_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-03-01", "weekend", 8.0, 1.0, "yes", "yes"),
    )
    conn.commit()


def _prep_v3(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP1", "测试员"))
    conn.execute(
        "INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("OP1", "2026-03-01", "weekend", 8.0, 1.0, "yes", "yes"),
    )
    conn.commit()


def _prep_v4(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP1", "测试员", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC1", "设备", "active"))
    conn.execute(
        "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        ("OP1", "MC1", " ExPeRt ", " YES "),
    )
    conn.commit()


def _prep_v5(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP1", "测试员"))
    conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC1", "设备"))
    conn.execute(
        "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        ("OP1", "MC1", "熟练", "是"),
    )
    conn.commit()


@pytest.mark.parametrize(
    ("run_fn", "prep", "expected_stderr"),
    [
        (run_v1, _prep_v1, "已清洗 Batches 的日期字段"),
        (run_v2, _prep_v2, "数据库迁移 v2：已将 WorkCalendar.day_type 的 weekend 统一为 holiday"),
        (run_v3, _prep_v3, "数据库迁移 v3：已将 OperatorCalendar.day_type 的 weekend 统一为 holiday"),
        (run_v4, _prep_v4, "数据库迁移 v4：已清洗 OperatorMachine.skill_level"),
        (run_v5, _prep_v5, "数据库迁移 v5：已修正 OperatorMachine.skill_level"),
    ],
)
def test_each_migration_falls_back_to_stderr_when_logger_is_broken(
    run_fn: Callable[..., None],
    prep: Callable[[sqlite3.Connection], None],
    expected_stderr: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    conn = _mem_conn()
    try:
        prep(conn)
        logger = _BrokenLogger()
        run_fn(conn, logger=logger)
        stderr = capsys.readouterr().err
        assert logger.calls, "预期 broken logger 至少被调用一次"
        assert expected_stderr in stderr, stderr
    finally:
        conn.close()


def test_v5_run_does_not_log_changed_rows_for_canonical_values() -> None:
    conn = _mem_conn()
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP1", "测试员"))
        conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC1", "设备"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP1", "MC1", "expert", "yes"),
        )
        conn.commit()

        logger = _CollectingLogger()
        before = int(conn.total_changes)
        run_v5(conn, logger=logger)
        after = int(conn.total_changes)

        assert after - before == 0
        assert not [msg for msg in logger.warnings if "已修正" in msg], logger.warnings
    finally:
        conn.close()


def test_ensure_schema_migration_entry_path_survives_broken_logger(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.TemporaryDirectory(prefix="aps_test_broken_logger_entry_") as tmpdir:
        db_path = os.path.join(tmpdir, "aps_test.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            _load_schema(conn)
            conn.execute("UPDATE SchemaVersion SET version=4 WHERE id=1")
            conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP1", "测试员"))
            conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC1", "设备"))
            conn.execute(
                "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
                ("OP1", "MC1", "熟练", "是"),
            )
            conn.commit()
        finally:
            conn.close()

        ensure_schema(db_path, logger=_BrokenLogger(), schema_path=SCHEMA_PATH, backup_dir=None)

        conn2 = sqlite3.connect(db_path)
        try:
            conn2.row_factory = sqlite3.Row
            row = conn2.execute(
                "SELECT skill_level, is_primary FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
                ("OP1", "MC1"),
            ).fetchone()
            version_row = conn2.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
            assert row is not None
            assert row["skill_level"] == "expert"
            assert row["is_primary"] == "yes"
            assert version_row is not None
            assert int(version_row["version"] or 0) >= CURRENT_SCHEMA_VERSION
        finally:
            conn2.close()

        stderr = capsys.readouterr().err
        assert "数据库已备份" in stderr or "数据库迁移完成" in stderr, stderr
