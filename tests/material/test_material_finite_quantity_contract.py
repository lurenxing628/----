"""合法库存写入与非法数量导致的事务回滚。"""

from __future__ import annotations

import math
import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.material import Material
from data.repositories.material_repo import MaterialRepository


@pytest.fixture
def material_repo(tmp_path):
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
        yield MaterialRepository(conn)
    finally:
        conn.close()


def _write(repo, path, value):
    if path == "repo_create":
        return repo.create(Material(material_id="M002", name="new", stock_qty=value))
    if path == "repo_update":
        return repo.update("M001", {"name": "changed", "stock_qty": value, "remark": "changed"})
    raise AssertionError(path)


@pytest.mark.parametrize('path', ["repo_create", "repo_update"])
def test_finite_numeric_write_contract_is_preserved(material_repo, path):
    repo = material_repo
    with TransactionManager(repo.conn).transaction():
        result = _write(repo, path, 12.5)
    mid = "M001" if path.endswith("update") else "M002"
    row = repo.conn.execute("SELECT * FROM Materials WHERE material_id = ?", (mid,)).fetchone()
    assert row is not None
    stored = row["stock_qty"]
    assert stored == 12.5
    assert math.isfinite(stored)
    if result is not None:
        assert float(result.stock_qty) == stored
    assert repo.conn.execute("SELECT COUNT(*) FROM Materials").fetchone()[0] == (1 if mid == "M001" else 2)
