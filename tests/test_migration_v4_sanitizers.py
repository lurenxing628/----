from __future__ import annotations

import sqlite3

import pytest

from core.infrastructure.migrations.common import MigrationOutcome
from core.infrastructure.migrations.v4 import _sanitize_field


class _CollectingLogger:
    def __init__(self) -> None:
        self.entries = []

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.entries.append(("warning", str(msg)))

    def error(self, msg: str, *args, **kwargs) -> None:
        self.entries.append(("error", str(msg)))


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_sanitize_field_keeps_v4_import_path_and_handles_core_values() -> None:
    conn = _conn()
    try:
        conn.execute("CREATE TABLE Items (id INTEGER PRIMARY KEY, status TEXT, note TEXT)")
        conn.executemany(
            "INSERT INTO Items (id, status, note) VALUES (?, ?, ?)",
            [
                (1, " YES ", "中文文本"),
                (2, "", "空字符串走默认值"),
                (3, None, "空值走默认值"),
                (4, "external", "已经规范的值不应变化"),
                (5, "中文文本", "中文枚举文本不应被破坏"),
            ],
        )

        outcome, changed, sample = _sanitize_field(
            conn,
            table="Items",
            field="status",
            pk_expr="CAST(id AS TEXT)",
            default="normal",
            logger=None,
        )

        rows = conn.execute("SELECT id, status, note FROM Items ORDER BY id").fetchall()
        assert outcome == MigrationOutcome.APPLIED
        assert changed == 3
        assert sample == ["1"]
        assert [(row["id"], row["status"], row["note"]) for row in rows] == [
            (1, "yes", "中文文本"),
            (2, "normal", "空字符串走默认值"),
            (3, "normal", "空值走默认值"),
            (4, "external", "已经规范的值不应变化"),
            (5, "中文文本", "中文枚举文本不应被破坏"),
        ]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("kwargs", "expected_log"),
    [
        ({"table": "Items;DROP", "field": "status", "pk_expr": "CAST(id AS TEXT)"}, "非法标识符"),
        ({"table": "Items", "field": "status--", "pk_expr": "CAST(id AS TEXT)"}, "非法标识符"),
        ({"table": "Items", "field": "status", "pk_expr": "id; DROP TABLE Items"}, "非法 pk_expr"),
    ],
)
def test_sanitize_field_rejects_unsafe_sql_fragments(kwargs: dict, expected_log: str) -> None:
    conn = _conn()
    try:
        conn.execute("CREATE TABLE Items (id INTEGER PRIMARY KEY, status TEXT)")
        logger = _CollectingLogger()

        outcome, changed, sample = _sanitize_field(conn, default="normal", logger=logger, **kwargs)

        assert outcome == MigrationOutcome.PARTIAL
        assert changed == 0
        assert sample == []
        assert any(expected_log in message for _level, message in logger.entries)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("table", "field"),
    [
        ("MissingItems", "status"),
        ("Items", "missing_status"),
    ],
)
def test_sanitize_field_skips_missing_table_or_column(table: str, field: str) -> None:
    conn = _conn()
    try:
        conn.execute("CREATE TABLE Items (id INTEGER PRIMARY KEY, status TEXT)")
        logger = _CollectingLogger()

        outcome, changed, sample = _sanitize_field(
            conn,
            table=table,
            field=field,
            pk_expr="CAST(id AS TEXT)",
            default="normal",
            logger=logger,
        )

        assert outcome == MigrationOutcome.SKIPPED
        assert changed == 0
        assert sample == []
        assert any("清洗已跳过" in message for _level, message in logger.entries)
    finally:
        conn.close()
