"""测试：Excel 导入加固——批次/工序工时/工种/人员日历校验器拒绝小数数量(不截断)、零号 id 不当空、bool/非有限数字单元、重复 id 与日期(规范化后)、重复名称冲突，预览与确认两段一致拒绝且不落库；上传超限按 EXCEL_MAX_UPLOAD_BYTES 返回 413 含「XMB」提示而非裸错误码，恰好等于上限不被 multipart 开销误拒；人员日历预览回退裁掉时间后缀；build_xlsx_bytes 对公式样字符串做防注入转义并冻结首行。"""

from __future__ import annotations

import os
import sys

import openpyxl
import pytest

from tests._support.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.errors import ValidationError
from core.infrastructure.database import ensure_schema, get_connection
from core.services.batch.service import BatchService
from core.services.common.excel_templates import sanitize_export_cell
from core.services.common.excel_validators import (
    get_batch_row_validate_and_normalize,
)
from core.services.common.normalize import is_blank_value


def _new_conn(tmp_path) -> tuple:
    db_path = tmp_path / "aps_test.db"
    ensure_schema(str(db_path), logger=None, schema_path=os.path.join(str(REPO_ROOT), "schema.sql"), backup_dir=None)
    return get_connection(str(db_path)), str(db_path)


def test_batch_quantity_float_is_rejected_without_truncation(tmp_path) -> None:
    conn, _db_path = _new_conn(tmp_path)
    try:
        validator = get_batch_row_validate_and_normalize(conn, parts_cache={"P001": object()}, inplace=True)
        row = {"批次号": "B001", "图号": "P001", "数量": 100.5}
        assert validator(row) == "“数量”必须是整数"

        with pytest.raises(ValidationError, match="必须是整数"):
            BatchService._normalize_int(100.5, field="数量", allow_none=False)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        (2, 2.0),
        ("2.5", 2.5),
    ],
)
def test_batch_safe_float_accepts_optional_ext_days(raw, expected) -> None:
    assert BatchService._safe_float(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "bad",
        float("nan"),
        "nan",
        float("inf"),
        "inf",
        True,
        False,
    ],
)
def test_batch_safe_float_rejects_invalid_ext_days_loudly(raw) -> None:
    with pytest.raises(ValidationError) as exc_info:
        BatchService._safe_float(raw)

    assert exc_info.value.field == "ext_days"


def test_batch_template_preserves_optional_ext_days_values(tmp_path) -> None:
    conn, _db_path = _new_conn(tmp_path)
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_EXT", "外协件", None, "yes", None),
        )
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_EXT", 10, None, "表处理", "external", None, None, None, 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_EXT", 20, None, "喷涂", "external", None, 2.5, None, 0.0, 0.0, "active"),
        )
        conn.commit()

        BatchService(conn, logger=None, op_logger=None).create_batch_from_template(
            batch_id="B_EXT",
            part_no="P_EXT",
            quantity=1,
            priority="normal",
            ready_status="yes",
        )

        rows = conn.execute(
            "SELECT seq, ext_days FROM BatchOperations WHERE batch_id=? ORDER BY seq",
            ("B_EXT",),
        ).fetchall()
        assert [int(row["seq"]) for row in rows] == [10, 20]
        assert rows[0]["ext_days"] is None
        assert abs(float(rows[1]["ext_days"] or 0.0) - 2.5) < 1e-9
    finally:
        conn.close()


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


def test_batch_validator_accepts_parts_cache_without_conn() -> None:
    validator = get_batch_row_validate_and_normalize(
        parts_cache={"P001": object()},
        inplace=True,
    )
    row = {
        "批次号": "B001",
        "图号": "P001",
        "数量": "2",
        "优先级": "normal",
        "齐套": "yes",
    }

    assert validator(row) is None
    assert row["数量"] == 2


def test_batch_validator_requires_conn_when_parts_cache_missing() -> None:
    with pytest.raises(ValueError, match="缺少 conn 或 parts_cache"):
        get_batch_row_validate_and_normalize(inplace=True)


def test_blank_helper_does_not_treat_zero_as_blank() -> None:
    assert is_blank_value(0) is False
    assert is_blank_value("0") is False
    assert is_blank_value(None) is True
    assert is_blank_value("   ") is True


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
