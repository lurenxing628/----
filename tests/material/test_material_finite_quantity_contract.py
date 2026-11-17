"""合法库存写入与非法数量导致的事务回滚；表单与导入写库存的上界与读取口径一致。"""

from __future__ import annotations

import math
import sqlite3
from io import BytesIO

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.material import Material
from data.repositories.material_repo import MaterialRepository
from tests.workbench.material_file_support import file_bytes


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


_MATERIALS = "/api/workbench/v1/entities/material"
_OVER = "库存数量超出有效数字范围。"


def _ok(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def test_material_form_stores_up_to_the_bound_that_reads_accept(app_client):
    # 表单写入与读取共用 is_stored_number：2^53-1 能存也能读出来，再大一点写入就拒绝，原值不动。
    context = _ok(app_client.get(_MATERIALS))["data"]["create_context"]
    saved = _ok(app_client.post(_MATERIALS + "/create", json={
        "request_key": "stock-bound-create-0001", "write_token": context["write_token"],
        "input": {"business_code": "MAT-MAX", "label": "max", "fields": {"stock_qty": 2 ** 53 - 1}}}))
    ref = saved["data"]["entity_ref"]
    detail = _ok(app_client.get(_MATERIALS + "/" + ref))["data"]
    assert detail["fields"]["stock_qty"] == 2 ** 53 - 1
    rejected = app_client.post(_MATERIALS + "/" + ref + "/update", json={
        "request_key": "stock-bound-update-0001", "write_token": detail["write_context"]["write_token"],
        "input": {"fields": {"stock_qty": 2 ** 53}}})
    assert rejected.status_code == 422, rejected.get_data(as_text=True)
    error = rejected.get_json()["error"]
    assert error["message"] == _OVER and error["fields"] == [{"message": _OVER, "path": "fields.stock_qty"}]
    assert _ok(app_client.get(_MATERIALS + "/" + ref))["data"]["fields"]["stock_qty"] == 2 ** 53 - 1


def test_material_import_rejects_stock_beyond_the_stored_bound(app_client):
    content = file_bytes([("MAT-MAX", "max", "9007199254740991"), ("MAT-OVER", "over", "9007199254740992"),
                          ("MAT-HUGE", "huge", "1e20")], "csv", ("物料编号", "名称", "库存数量"))
    preview = _ok(app_client.post("/api/workbench/v1/imports/material/preview", data={
        "file": (BytesIO(content), "input.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data"))["data"]
    first, *over = preview["rows"]
    assert first["errors"] == [] and first["after"]["stock_qty"] == 2 ** 53 - 1
    assert [[(error["field"], error["message"]) for error in row["errors"]] for row in over] == [
        [("fields.stock_qty", _OVER)], [("fields.stock_qty", _OVER)]]
    assert preview["can_confirm"] is False
