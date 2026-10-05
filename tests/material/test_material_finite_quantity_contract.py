"""合法库存写入与非法数量导致的事务回滚。"""

from __future__ import annotations

import math
import sqlite3
from unittest.mock import Mock

import pytest

from core.errors import ValidationError
from core.services.material.material_service import MaterialService


@pytest.fixture
def material_service(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "materials.db"))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE Materials (material_id TEXT PRIMARY KEY, name TEXT NOT NULL,"
        " spec TEXT, unit TEXT, stock_qty REAL DEFAULT 0, status TEXT DEFAULT 'active',"
        " remark TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute("INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M001', 'original', 5)")
    conn.commit()
    try:
        yield MaterialService(conn, op_logger=Mock())
    finally:
        conn.close()


def _write(service, path, value):
    if path == "service_create":
        return service.create("M002", "new", stock_qty=value)
    if path == "service_update":
        return service.update("M001", name="changed", stock_qty=value, remark="changed")
    if path == "repo_update":
        return service.repo.update("M001", {"name": "changed", "stock_qty": value, "remark": "changed"})
    raise AssertionError(path)


def _snapshot(conn):
    return [tuple(row) for row in conn.execute("SELECT *, typeof(stock_qty) FROM Materials ORDER BY material_id")]


@pytest.mark.parametrize('path', ["service_create", "repo_update"])
@pytest.mark.parametrize('value', [12.5])
def test_finite_numeric_write_contract_is_preserved(material_service, path, value):
    service = material_service
    result = _write(service, path, value)
    mid = "M001" if path.endswith("update") else "M002"
    stored = service.get(mid).stock_qty
    assert stored == float(value)
    assert math.isfinite(stored)
    if result is not None:
        assert float(result.stock_qty) == stored
    assert len(service.list()) == (1 if mid == "M001" else 2)


@pytest.mark.parametrize('path', ["service_update"])
def test_invalid_quantity_rolls_back_prior_writes_in_outer_transaction(material_service, path):
    service = material_service
    before = _snapshot(service.conn)
    expected_error = ValidationError if path.startswith("service") else ValueError
    with pytest.raises(expected_error):
        with service.tx.transaction():
            service.create("M003", "earlier", stock_qty=3)
            _write(service, path, "Infinity")
    assert _snapshot(service.conn) == before
    assert not service.conn.in_transaction
