"""回归测试：MaterialRepository.update 的 stock_qty 数字转换 loud 契约（R40/O28 收口）——非数字坏值（旁路绕过 service 强校验直调 repo 时）必须自然抛 ValueError 且坏值不落库，绝不允许改回「except 吞错后把原始坏值写进 Materials.stock_qty（REAL 列）」的静默兜底；空串/None 表示「不改」的跳过语义与合法数字的正常更新不受影响。"""

from __future__ import annotations

import sqlite3

import pytest

from data.repositories.material_repo import MaterialRepository


def _make_repo() -> MaterialRepository:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE Materials ("
        " material_id TEXT PRIMARY KEY, name TEXT, spec TEXT, unit TEXT,"
        " stock_qty REAL, status TEXT, remark TEXT,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO Materials (material_id, name, spec, unit, stock_qty, status, remark)"
        " VALUES ('M001', '钢板', '10mm', '张', 5.0, 'active', '')"
    )
    conn.commit()
    return MaterialRepository(conn)


def _stock_qty(repo: MaterialRepository) -> float:
    return float(repo.fetchvalue("SELECT stock_qty FROM Materials WHERE material_id = 'M001'"))


def test_update_raises_on_non_numeric_stock_qty_and_keeps_db_clean() -> None:
    repo = _make_repo()
    with pytest.raises(ValueError):
        repo.update("M001", {"stock_qty": "abc"})
    assert _stock_qty(repo) == 5.0, "坏值必须被 loud 拒绝，库存原值不得被污染"


def test_update_blank_or_none_stock_qty_means_no_change() -> None:
    repo = _make_repo()
    repo.update("M001", {"stock_qty": None, "name": "钢板A"})
    repo.update("M001", {"stock_qty": "   "})
    assert _stock_qty(repo) == 5.0, "空串/None 表示不改，跳过语义不得受 R40 收口影响"


def test_update_valid_numeric_string_still_updates() -> None:
    repo = _make_repo()
    repo.update("M001", {"stock_qty": "12.5"})
    assert _stock_qty(repo) == 12.5, "合法数字字符串应正常转换落库（happy path 防误伤）"
