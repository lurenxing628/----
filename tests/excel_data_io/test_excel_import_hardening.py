"""批次复制保留外协天数，导出文字防止公式注入。"""

from __future__ import annotations

import os
import sys

from tests._support.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infrastructure.database import ensure_schema, get_connection
from core.services.batch.service import BatchService
from core.services.common.excel_templates import sanitize_export_cell


def _new_conn(tmp_path) -> tuple:
    db_path = tmp_path / "aps_test.db"
    ensure_schema(str(db_path), logger=None, schema_path=os.path.join(str(REPO_ROOT), "schema.sql"), backup_dir=None)
    return get_connection(str(db_path)), str(db_path)


def test_batch_copy_preserves_optional_ext_days_values(tmp_path) -> None:
    conn, _db_path = _new_conn(tmp_path)
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_COPY", "复制件", None, "yes", None),
        )
        conn.execute(
            """
            INSERT INTO Batches
            (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_SRC", "P_COPY", "复制件", 1, None, "normal", "yes", None, "pending", None),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_SRC_10", "B_SRC", None, 10, None, "表处理", "external", None, None, None, 0.0, 0.0, None, "scheduled"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_SRC_20", "B_SRC", None, 20, None, "喷涂", "external", None, None, None, 0.0, 0.0, 2.5, "scheduled"),
        )
        conn.commit()

        BatchService(conn, logger=None, op_logger=None).copy_batch("B_SRC", "B_DST")

        rows = conn.execute(
            "SELECT seq, ext_days, status FROM BatchOperations WHERE batch_id=? ORDER BY seq",
            ("B_DST",),
        ).fetchall()
        assert [int(row["seq"]) for row in rows] == [10, 20]
        assert rows[0]["ext_days"] is None
        assert abs(float(rows[1]["ext_days"] or 0.0) - 2.5) < 1e-9
        assert {row["status"] for row in rows} == {"pending"}
    finally:
        conn.close()


def test_export_cells_escape_formula_like_strings() -> None:
    """导出到 Excel 的文字里，四个会被当公式起头的字符必须先加单引号。

    原来这条挂在 build_xlsx_bytes 上，那个构建器 2026-09-21 随旧模板清单一起退役了；
    防注入本身没退役——排产实际导出、校准导出、报表导出、报表 xlsx 四处生产代码都
    直接用 sanitize_export_cell，所以契约改挂在它身上。
    """
    assert sanitize_export_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_export_cell("+SUM(1,1)") == "'+SUM(1,1)"
    assert sanitize_export_cell("-1") == "'-1"
    assert sanitize_export_cell("@A1") == "'@A1"
    assert sanitize_export_cell("正常文字") == "正常文字"
    assert sanitize_export_cell(123) == 123
    # 控制字符会让 openpyxl 写出打不开的文件，一并剔掉；制表和换行保留。
    assert sanitize_export_cell("甲\x00乙\x07") == "甲乙"
    assert sanitize_export_cell("甲\t乙\n丙") == "甲\t乙\n丙"
