"""回归测试：SupplierService 对非法 default_days 不静默——create 传非数字（"abc"）抛 ValidationError（提示含“默认周期”）且不落库，update 传空串抛 ValidationError（提示含“不能为空”）且不覆盖原有 default_days；合法 default_days=2.5 正常创建并持久化。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.process.supplier_service import SupplierService
from tests._support.paths import REPO_ROOT


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = REPO_ROOT / "schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def _message(exc: ValidationError) -> str:
    return getattr(exc, "message", str(exc))


def test_supplier_service_invalid_default_days_rejected_on_create_and_update() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        svc = SupplierService(conn, logger=None, op_logger=None)

        with pytest.raises(ValidationError) as create_exc:
            svc.create("S_BAD", "坏默认周期供应商", default_days="abc", status="active")
        assert "默认周期" in _message(create_exc.value)
        count_row = conn.execute("SELECT COUNT(1) AS cnt FROM Suppliers WHERE supplier_id=?", ("S_BAD",)).fetchone()
        assert count_row is not None and int(count_row["cnt"] or 0) == 0

        created = svc.create("S_OK", "正常供应商", default_days=2.5, status="active")
        assert created.supplier_id == "S_OK"

        with pytest.raises(ValidationError) as update_exc:
            svc.update("S_OK", default_days="")
        assert "不能为空" in _message(update_exc.value)

        row = conn.execute("SELECT default_days FROM Suppliers WHERE supplier_id=?", ("S_OK",)).fetchone()
        assert row is not None
        assert abs(float(row["default_days"] or 0.0) - 2.5) < 1e-9
    finally:
        conn.close()
