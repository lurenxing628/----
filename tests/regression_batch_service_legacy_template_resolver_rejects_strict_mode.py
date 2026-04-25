from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _load_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def test_batch_service_legacy_template_resolver_rejects_strict_mode() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.scheduler.batch_service import BatchService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        _load_schema(conn)
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_ROUTE", "路线件", "10表处理", "no"),
        )
        conn.commit()

        def legacy_resolver(part_no, part_name, route_raw, no_tx):
            return None

        svc = BatchService(conn, template_resolver=legacy_resolver)
        with pytest.raises(BusinessError) as exc_info:
            svc.create_batch_from_template(
                batch_id="B_STRICT_LEGACY",
                part_no="P_ROUTE",
                quantity=1,
                priority="normal",
                ready_status="yes",
                strict_mode=True,
            )

        err = exc_info.value
        assert err.code == ErrorCode.ROUTE_PARSE_ERROR
        assert "不支持严格模式" in err.message

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT_LEGACY",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0
    finally:
        conn.close()
