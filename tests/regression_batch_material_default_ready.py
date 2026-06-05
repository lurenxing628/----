"""回归测试：批次物料就绪状态的默认与联动契约——Batches.ready_status 默认 yes 而 BatchMaterials.ready_status 默认 no；
BatchMaterialService.add_requirement 空 available_qty 回填为 required_qty 并整批就绪、显式 0 保持未就绪、update 空值保留旧值、删最后一条需求恢复批次默认就绪（v8 前后行为一致）。"""

from __future__ import annotations

from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.migration_state import detect_schema_is_current
from core.infrastructure.migrations.v8 import run as run_v8
from core.services.material.batch_material_service import BatchMaterialService

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _prepare_db(tmp_path):
    db_path = tmp_path / "aps_batch_material_default_ready.db"
    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(db_path))
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES (?, ?)", ("P001", "测试零件"))
    conn.execute(
        """
        INSERT INTO Batches(batch_id, part_no, quantity, ready_status, ready_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("B001", "P001", 1, "yes", None, "pending"),
    )
    conn.execute("INSERT INTO Materials(material_id, name, status) VALUES (?, ?, ?)", ("M001", "测试物料", "active"))
    conn.commit()
    return conn


def _batch_row(conn):
    return conn.execute(
        "SELECT ready_status, ready_date FROM Batches WHERE batch_id = ?",
        ("B001",),
    ).fetchone()


def _material_row(conn):
    return conn.execute(
        "SELECT required_qty, available_qty, ready_status FROM BatchMaterials WHERE batch_id = ? AND material_id = ?",
        ("B001", "M001"),
    ).fetchone()


def _column_default(conn, *, table: str, column: str) -> str:
    for row in conn.execute(f"PRAGMA table_info({table})").fetchall():
        if row["name"] == column:
            return str(row["dflt_value"] or "").strip().strip("'\"").lower()
    raise AssertionError(f"缺少字段：{table}.{column}")


def test_batch_material_schema_default_status_is_conservative_no(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        assert detect_schema_is_current(conn) is True
        assert _column_default(conn, table="Batches", column="ready_status") == "yes"
        assert _column_default(conn, table="BatchMaterials", column="ready_status") == "no"

        conn.execute(
            """
            INSERT INTO BatchMaterials(batch_id, material_id, required_qty)
            VALUES (?, ?, ?)
            """,
            ("B001", "M001", 10),
        )
        row = _material_row(conn)
        assert float(row["available_qty"]) == 0.0
        assert row["ready_status"] == "no"
    finally:
        conn.close()


def test_add_requirement_blank_available_qty_defaults_to_ready(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        svc = BatchMaterialService(conn, logger=None, op_logger=None)

        svc.add_requirement("B001", "M001", required_qty="10", available_qty="")

        material = _material_row(conn)
        batch = _batch_row(conn)
        assert float(material["available_qty"]) == 10.0
        assert material["ready_status"] == "yes"
        assert batch["ready_status"] == "yes"
        assert batch["ready_date"] is None
    finally:
        conn.close()


def test_add_requirement_after_v8_blank_available_qty_still_defaults_to_ready(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        run_v8(conn, logger=None)
        svc = BatchMaterialService(conn, logger=None, op_logger=None)

        svc.add_requirement("B001", "M001", required_qty="10", available_qty="")

        material = _material_row(conn)
        batch = _batch_row(conn)
        assert float(material["available_qty"]) == 10.0
        assert material["ready_status"] == "yes"
        assert batch["ready_status"] == "yes"
        assert batch["ready_date"] is None
    finally:
        conn.close()


def test_add_requirement_explicit_zero_remains_not_ready(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        svc = BatchMaterialService(conn, logger=None, op_logger=None)

        svc.add_requirement("B001", "M001", required_qty="10", available_qty="0")

        material = _material_row(conn)
        batch = _batch_row(conn)
        assert float(material["available_qty"]) == 0.0
        assert material["ready_status"] == "no"
        assert batch["ready_status"] == "no"
        assert batch["ready_date"] is None
    finally:
        conn.close()


def test_update_blank_available_qty_preserves_existing_value(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        svc = BatchMaterialService(conn, logger=None, op_logger=None)
        svc.add_requirement("B001", "M001", required_qty="10", available_qty="3")
        bm_id = conn.execute("SELECT id FROM BatchMaterials WHERE batch_id = ?", ("B001",)).fetchone()["id"]

        svc.update_requirement(bm_id, required_qty="10", available_qty="")

        material = _material_row(conn)
        batch = _batch_row(conn)
        assert float(material["available_qty"]) == 3.0
        assert material["ready_status"] == "no"
        assert batch["ready_status"] == "no"
    finally:
        conn.close()


def test_delete_last_requirement_restores_default_ready(tmp_path) -> None:
    conn = _prepare_db(tmp_path)
    try:
        svc = BatchMaterialService(conn, logger=None, op_logger=None)
        svc.add_requirement("B001", "M001", required_qty="10", available_qty="0")
        bm_id = conn.execute("SELECT id FROM BatchMaterials WHERE batch_id = ?", ("B001",)).fetchone()["id"]

        svc.delete_requirement(bm_id)

        batch = _batch_row(conn)
        assert batch["ready_status"] == "yes"
        assert batch["ready_date"] is None
    finally:
        conn.close()
