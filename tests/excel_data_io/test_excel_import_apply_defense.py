"""回归测试：设备/工种/操作员/供应商/零件工时五类台账 Excel 导入服务 apply_preview_rows 的写库防御——非法状态/缺名整体回滚或行级记错、字段去空与状态/备注规范化、班组按 ID 或名称匹配及空值清空、缺列保留既有值、零值 ID 不当空、空周期拒绝，以及零件工时对 NaN/Inf/解析错的行级拦截与意外异常整体回滚。"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Tuple

import pytest

from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.equipment.machine_excel_import_service import MachineExcelImportService
from core.services.personnel.operator_excel_import_service import OperatorExcelImportService
from core.services.process.op_type_excel_import_service import OpTypeExcelImportService
from core.services.process.part_operation_hours_excel_import_service import (
    PartOperationHoursExcelImportService,
)
from core.services.process.supplier_excel_import_service import SupplierExcelImportService

# 合并自 6 个 main-style 文件（簇 excel_import_apply_defense）：
#   - test_machine_excel_import_apply_defense.py
#   - test_op_type_excel_import_apply_defense.py
#   - test_operator_excel_import_normalization.py
#   - test_supplier_excel_import_remark_normalization.py
#   - test_part_operation_hours_import_apply_defense.py
#   - test_part_operation_hours_import_apply_mixed_rows.py
# A 型（machine/op_type/operator/supplier）签名 apply_preview_rows(rows, *, mode, existing_ids)；
# B 型（part_operation_hours）签名 apply_preview_rows(rows)，异构，不整簇压平 parametrize。
# schema/连接样板统一收口到 conftest 共享 fixture（schema_conn / mem_conn）。


def _pr(
    data: Dict[str, Any], *, status: RowStatus = RowStatus.NEW, row_num: int = 2
) -> ImportPreviewRow:
    return ImportPreviewRow(row_num=row_num, status=status, data=dict(data or {}), message="")


def _count_machines(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(1) AS n FROM Machines").fetchone()
    assert row is not None
    return int(row["n"] or 0)


def _insert_team(conn: sqlite3.Connection, team_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)",
        (team_id, name, "active"),
    )


def _seed_part_and_internal_op(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
        ("P001", "Part-001", None, "no", None),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (
            part_no, seq, op_type_id, op_type_name, source,
            supplier_id, ext_days, ext_group_id,
            setup_hours, unit_hours, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 1, None, "OP1", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.commit()


def _get_hours(conn: sqlite3.Connection, *, part_no: str, seq: int) -> Tuple[float, float]:
    row = conn.execute(
        "SELECT setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
        (str(part_no), int(seq)),
    ).fetchone()
    assert row is not None
    return float(row["setup_hours"] or 0.0), float(row["unit_hours"] or 0.0)


# ============================================================================
# machine（A 型，ValidationError 整体回滚）
# ============================================================================


def test_machine_apply_preview_rows_invalid_status_raises_and_rolls_back_all_changes(
    schema_conn,
) -> None:
    conn = schema_conn
    svc = MachineExcelImportService(conn)
    preview_rows = [
        _pr({"设备编号": "MC001", "设备名称": "CNC-01", "状态": "active"}, row_num=2),
        _pr({"设备编号": "MC002", "设备名称": "CNC-02", "状态": "BAD"}, row_num=3),
    ]

    expected_message = "状态不合法，可填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    with pytest.raises(ValidationError, match="状态不合法") as exc_info:
        svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

    assert exc_info.value.message == expected_message
    assert exc_info.value.field == "状态"
    assert _count_machines(conn) == 0


def test_machine_apply_preview_rows_missing_name_raises_validation_error(schema_conn) -> None:
    conn = schema_conn
    svc = MachineExcelImportService(conn)
    preview_rows = [
        _pr({"设备编号": "MC001", "设备名称": "", "状态": "active"}, row_num=2),
    ]

    with pytest.raises(ValidationError, match="设备名称不能为空") as exc_info:
        svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

    assert exc_info.value.message == "设备名称不能为空"
    assert exc_info.value.field == "设备名称"
    assert _count_machines(conn) == 0


def test_machine_apply_preview_rows_missing_status_raises_specific_message(schema_conn) -> None:
    conn = schema_conn
    svc = MachineExcelImportService(conn)
    preview_rows = [
        _pr({"设备编号": "MC001", "设备名称": "CNC-01", "状态": ""}, row_num=2),
    ]

    expected_message = "状态不能为空，请填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    with pytest.raises(ValidationError, match="状态不能为空") as e:
        svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())

    assert e.value.message == expected_message
    assert e.value.field == "状态"
    assert _count_machines(conn) == 0


def test_machine_apply_preview_rows_valid_rows_commit_and_trim_fields(schema_conn) -> None:
    conn = schema_conn
    svc = MachineExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [
            _pr({"设备编号": " MC001 ", "设备名称": " CNC-01 ", "状态": "可用"}, row_num=2),
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    assert int(stats.get("total_rows", 0)) == 1, stats
    assert int(stats.get("new_count", 0)) == 1, stats
    assert int(stats.get("error_count", 0)) == 0, stats

    row = conn.execute(
        "SELECT machine_id, name, op_type_id, status FROM Machines WHERE machine_id=?",
        ("MC001",),
    ).fetchone()
    assert row is not None
    assert row["machine_id"] == "MC001"
    assert row["name"] == "CNC-01"
    assert row["op_type_id"] is None
    assert row["status"] == "active"


def test_machine_apply_preview_rows_update_without_team_column_preserves_existing_team_id(
    schema_conn,
) -> None:
    conn = schema_conn
    _insert_team(conn, "TEAM-01", "车工一组")
    conn.execute(
        "INSERT INTO Machines (machine_id, name, status, team_id) VALUES (?, ?, ?, ?)",
        ("MC001", "CNC-01", "active", "TEAM-01"),
    )
    conn.commit()

    svc = MachineExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [
            _pr(
                {"设备编号": "MC001", "设备名称": "CNC-01-更新", "状态": "active"},
                status=RowStatus.UPDATE,
                row_num=2,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"MC001"},
    )
    assert int(stats.get("update_count", 0)) == 1, stats

    row = conn.execute(
        "SELECT name, status, team_id FROM Machines WHERE machine_id=?",
        ("MC001",),
    ).fetchone()
    assert row is not None
    assert row["name"] == "CNC-01-更新"
    assert row["status"] == "active"
    assert row["team_id"] == "TEAM-01"


def test_machine_apply_preview_rows_team_accepts_id_or_name_and_blank_clears(schema_conn) -> None:
    conn = schema_conn
    _insert_team(conn, "TEAM-01", "车工一组")
    _insert_team(conn, "TEAM-02", "车工二组")
    conn.commit()

    svc = MachineExcelImportService(conn)
    svc.apply_preview_rows(
        [
            _pr(
                {"设备编号": "MC001", "设备名称": "CNC-01", "状态": "active", "班组": "TEAM-01"},
                row_num=2,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    row1 = conn.execute(
        "SELECT team_id FROM Machines WHERE machine_id=?",
        ("MC001",),
    ).fetchone()
    assert row1 is not None
    assert row1["team_id"] == "TEAM-01"

    svc.apply_preview_rows(
        [
            _pr(
                {"设备编号": "MC001", "设备名称": "CNC-01", "状态": "active", "班组": "车工二组"},
                status=RowStatus.UPDATE,
                row_num=3,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"MC001"},
    )
    row2 = conn.execute(
        "SELECT team_id FROM Machines WHERE machine_id=?",
        ("MC001",),
    ).fetchone()
    assert row2 is not None
    assert row2["team_id"] == "TEAM-02"

    svc.apply_preview_rows(
        [
            _pr(
                {"设备编号": "MC001", "设备名称": "CNC-01", "状态": "active", "班组": ""},
                status=RowStatus.UPDATE,
                row_num=4,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"MC001"},
    )
    row3 = conn.execute(
        "SELECT team_id FROM Machines WHERE machine_id=?",
        ("MC001",),
    ).fetchone()
    assert row3 is not None
    assert row3["team_id"] is None


# ============================================================================
# op_type（A 型，行级错误不回滚）
# ============================================================================


def test_op_type_apply_preview_rows_commits_valid_rows_and_keeps_row_errors(schema_conn) -> None:
    conn = schema_conn
    svc = OpTypeExcelImportService(conn)
    preview_rows = [
        _pr({"工种ID": "OT001", "工种名称": "数车", "归属": "内部"}, row_num=2),
        _pr({"工种ID": "OT002", "工种名称": "数铣", "归属": "BAD"}, row_num=3),
        _pr({"工种ID": "OT003", "工种名称": "", "归属": "internal"}, row_num=4),
    ]

    stats = svc.apply_preview_rows(preview_rows, mode=ImportMode.OVERWRITE, existing_ids=set())
    assert int(stats.get("total_rows", 0)) == 3, stats
    assert int(stats.get("new_count", 0)) == 1, stats
    assert int(stats.get("error_count", 0)) == 2, stats

    rows = conn.execute("SELECT op_type_id, name, category FROM OpTypes ORDER BY op_type_id").fetchall()
    assert [(r["op_type_id"], r["name"], r["category"]) for r in rows] == [("OT001", "数车", "internal")]


def test_op_type_apply_preview_rows_rejects_duplicate_name_on_create(schema_conn) -> None:
    conn = schema_conn
    conn.execute(
        "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
        ("OT001", "数车", "internal"),
    )
    conn.commit()

    svc = OpTypeExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [_pr({"工种ID": "OT002", "工种名称": "数车", "归属": "internal"}, row_num=2)],
        mode=ImportMode.OVERWRITE,
        existing_ids={"OT001"},
    )

    assert int(stats.get("new_count", 0)) == 0, stats
    assert int(stats.get("error_count", 0)) == 1, stats
    assert "工种名称“数车”已存在" in str((stats.get("errors_sample") or [{}])[0].get("message") or "")

    rows = conn.execute("SELECT op_type_id, name FROM OpTypes ORDER BY op_type_id").fetchall()
    assert [(r["op_type_id"], r["name"]) for r in rows] == [("OT001", "数车")]


def test_op_type_apply_preview_rows_rejects_duplicate_name_on_update(schema_conn) -> None:
    conn = schema_conn
    conn.execute(
        "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
        ("OT001", "数车", "internal"),
    )
    conn.execute(
        "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
        ("OT002", "数铣", "internal"),
    )
    conn.commit()

    svc = OpTypeExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [_pr({"工种ID": "OT002", "工种名称": "数车", "归属": "internal"}, status=RowStatus.UPDATE, row_num=2)],
        mode=ImportMode.OVERWRITE,
        existing_ids={"OT001", "OT002"},
    )

    assert int(stats.get("update_count", 0)) == 0, stats
    assert int(stats.get("error_count", 0)) == 1, stats
    assert "工种名称“数车”已存在" in str((stats.get("errors_sample") or [{}])[0].get("message") or "")

    rows = conn.execute("SELECT op_type_id, name FROM OpTypes ORDER BY op_type_id").fetchall()
    assert [(r["op_type_id"], r["name"]) for r in rows] == [("OT001", "数车"), ("OT002", "数铣")]


# ============================================================================
# operator（A 型，规范化 + 班组 + 备注 normalize）
# ============================================================================


def test_operator_excel_import_strips_name_and_normalizes_remark(schema_conn) -> None:
    conn = schema_conn
    svc = OperatorExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [
            _pr(
                {"工号": " OP001 ", "姓名": "  张三  ", "状态": "Active", "备注": "  示例备注  "},
                row_num=2,
            ),
            _pr(
                {"工号": "OP002", "姓名": "李四", "状态": "INACTIVE", "备注": "   "},
                row_num=3,
            ),
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    assert int(stats.get("total_rows", 0)) == 2, stats
    assert int(stats.get("new_count", 0)) == 2, stats
    assert int(stats.get("error_count", 0)) == 0, stats

    r1 = conn.execute(
        "SELECT operator_id, name, status, remark FROM Operators WHERE operator_id=?",
        ("OP001",),
    ).fetchone()
    assert r1 is not None
    assert r1["operator_id"] == "OP001"
    assert r1["name"] == "张三"
    assert r1["status"] == "active"
    assert r1["remark"] == "示例备注"

    r2 = conn.execute(
        "SELECT operator_id, name, status, remark FROM Operators WHERE operator_id=?",
        ("OP002",),
    ).fetchone()
    assert r2 is not None
    assert r2["operator_id"] == "OP002"
    assert r2["name"] == "李四"
    assert r2["status"] == "inactive"
    assert r2["remark"] is None


def test_operator_excel_import_update_without_team_column_preserves_existing_team_id(
    schema_conn,
) -> None:
    conn = schema_conn
    _insert_team(conn, "TEAM-01", "车工一组")
    conn.execute(
        "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
        ("OP001", "张三", "active", "TEAM-01", "旧备注"),
    )
    conn.commit()

    svc = OperatorExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [
            _pr(
                {"工号": "OP001", "姓名": "张三-更新", "状态": "active", "备注": "新备注"},
                status=RowStatus.UPDATE,
                row_num=2,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"OP001"},
    )
    assert int(stats.get("update_count", 0)) == 1, stats

    row = conn.execute(
        "SELECT name, status, team_id, remark FROM Operators WHERE operator_id=?",
        ("OP001",),
    ).fetchone()
    assert row is not None
    assert row["name"] == "张三-更新"
    assert row["status"] == "active"
    assert row["team_id"] == "TEAM-01"
    assert row["remark"] == "新备注"


def test_operator_excel_import_team_accepts_id_or_name_and_blank_clears(schema_conn) -> None:
    conn = schema_conn
    _insert_team(conn, "TEAM-01", "车工一组")
    _insert_team(conn, "TEAM-02", "车工二组")
    conn.commit()

    svc = OperatorExcelImportService(conn)
    svc.apply_preview_rows(
        [
            _pr(
                {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "TEAM-01", "备注": "首次导入"},
                row_num=2,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    row1 = conn.execute(
        "SELECT team_id, remark FROM Operators WHERE operator_id=?",
        ("OP001",),
    ).fetchone()
    assert row1 is not None
    assert row1["team_id"] == "TEAM-01"
    assert row1["remark"] == "首次导入"

    svc.apply_preview_rows(
        [
            _pr(
                {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "车工二组", "备注": "按名称切换"},
                status=RowStatus.UPDATE,
                row_num=3,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"OP001"},
    )
    row2 = conn.execute(
        "SELECT team_id, remark FROM Operators WHERE operator_id=?",
        ("OP001",),
    ).fetchone()
    assert row2 is not None
    assert row2["team_id"] == "TEAM-02"
    assert row2["remark"] == "按名称切换"

    svc.apply_preview_rows(
        [
            _pr(
                {"工号": "OP001", "姓名": "张三", "状态": "active", "班组": "", "备注": "显式清空"},
                status=RowStatus.UPDATE,
                row_num=4,
            )
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids={"OP001"},
    )
    row3 = conn.execute(
        "SELECT team_id, remark FROM Operators WHERE operator_id=?",
        ("OP001",),
    ).fetchone()
    assert row3 is not None
    assert row3["team_id"] is None
    assert row3["remark"] == "显式清空"


# ============================================================================
# supplier（A 型，零值 id + 备注 normalize + 缺列保留 + 空周期拒绝）
# ============================================================================


@pytest.mark.parametrize("id_column", ["供应商编号", "供应商ID"])
def test_supplier_excel_import_does_not_treat_zero_id_as_blank(id_column: str, schema_conn) -> None:
    conn = schema_conn
    svc = SupplierExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [_pr({id_column: 0, "名称": "零号供应商", "默认周期": 1, "状态": "启用"}, row_num=2)],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )

    row = conn.execute("SELECT supplier_id, name FROM Suppliers WHERE supplier_id = ?", ("0",)).fetchone()
    assert row is not None
    assert dict(row) == {"supplier_id": "0", "name": "零号供应商"}
    assert stats["new_count"] == 1
    assert stats["error_count"] == 0


def test_supplier_excel_import_normalizes_remark_text(schema_conn) -> None:
    conn = schema_conn
    svc = SupplierExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [
            _pr({"供应商ID": " S001 ", "名称": " 外协-标印厂 ", "默认周期": 2, "状态": None, "备注": "  abc  "}, row_num=2),
            _pr({"供应商ID": "S002", "名称": "外协-热处理厂", "默认周期": 1.0, "状态": "启用", "备注": "   "}, row_num=3),
        ],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    assert int(stats.get("total_rows", 0)) == 2, stats
    assert int(stats.get("new_count", 0)) == 2, stats
    assert int(stats.get("error_count", 0)) == 0, stats

    r1 = conn.execute(
        "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
        ("S001",),
    ).fetchone()
    assert r1 is not None
    assert r1["supplier_id"] == "S001"
    assert r1["name"] == "外协-标印厂"
    assert float(r1["default_days"] or 0) == 2.0
    assert r1["status"] == "active"
    assert r1["remark"] == "abc"

    r2 = conn.execute(
        "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
        ("S002",),
    ).fetchone()
    assert r2 is not None
    assert r2["supplier_id"] == "S002"
    assert r2["name"] == "外协-热处理厂"
    assert float(r2["default_days"] or 0) == 1.0
    assert r2["status"] == "active"
    assert r2["remark"] is None


def test_supplier_excel_import_overwrite_preserves_existing_status_and_remark_when_columns_missing(
    schema_conn,
) -> None:
    conn = schema_conn
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, default_days, status, remark) VALUES (?, ?, ?, ?, ?)",
        ("S001", "旧供应商", 2.0, "inactive", "keep me"),
    )
    conn.commit()

    svc = SupplierExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [_pr({"供应商ID": "S001", "名称": "新供应商", "默认周期": 3.5}, status=RowStatus.UPDATE, row_num=2)],
        mode=ImportMode.OVERWRITE,
        existing_ids={"S001"},
    )
    assert int(stats.get("total_rows", 0)) == 1, stats
    assert int(stats.get("update_count", 0)) == 1, stats
    assert int(stats.get("error_count", 0)) == 0, stats

    row = conn.execute(
        "SELECT supplier_id, name, default_days, status, remark FROM Suppliers WHERE supplier_id=?",
        ("S001",),
    ).fetchone()
    assert row is not None
    assert row["supplier_id"] == "S001"
    assert row["name"] == "新供应商"
    assert float(row["default_days"] or 0) == 3.5
    assert row["status"] == "inactive"
    assert row["remark"] == "keep me"


def test_supplier_excel_import_rejects_blank_default_days(schema_conn) -> None:
    conn = schema_conn
    svc = SupplierExcelImportService(conn)
    stats = svc.apply_preview_rows(
        [_pr({"供应商ID": "S003", "名称": "空白周期供应商", "默认周期": ""}, row_num=2)],
        mode=ImportMode.OVERWRITE,
        existing_ids=set(),
    )
    assert int(stats.get("total_rows", 0)) == 1, stats
    assert int(stats.get("new_count", 0)) == 0, stats
    assert int(stats.get("error_count", 0)) == 1, stats
    errors_sample = stats.get("errors_sample") or []
    assert errors_sample and "默认周期" in str(errors_sample[0].get("message") or "")

    row = conn.execute("SELECT COUNT(1) AS cnt FROM Suppliers WHERE supplier_id=?", ("S003",)).fetchone()
    assert row is not None and int(row["cnt"] or 0) == 0


# ============================================================================
# part_operation_hours — defense（B 型，_parse_write_row 静态 + NaN/Inf）
# ============================================================================


def test_part_op_hours_parse_write_row_accepts_integer_float_string_forms() -> None:
    parsed, err = PartOperationHoursExcelImportService._parse_write_row(
        _pr({"图号": "P001", "工序": 5.0, "换型时间(h)": 1.0, "单件工时(h)": 0.25}, status=RowStatus.UPDATE)
    )
    assert err is None
    assert parsed == ("P001", 5, 1.0, 0.25)

    parsed, err = PartOperationHoursExcelImportService._parse_write_row(
        _pr({"图号": "P001", "工序": "5.0", "换型时间(h)": "1.0", "单件工时(h)": "0.25"}, status=RowStatus.UPDATE)
    )
    assert err is None
    assert parsed == ("P001", 5, 1.0, 0.25)

    parsed, err = PartOperationHoursExcelImportService._parse_write_row(
        _pr({"图号": "P001", "工序": "5e0"}, status=RowStatus.UPDATE)
    )
    assert parsed is None
    assert err is not None


def test_part_op_hours_apply_preview_rows_turns_nan_inf_into_row_errors(mem_conn) -> None:
    conn = mem_conn
    svc = PartOperationHoursExcelImportService(conn)
    preview_rows = [
        _pr({"图号": "P001", "工序": 1, "换型时间(h)": float("nan"), "单件工时(h)": 0.1}, status=RowStatus.UPDATE, row_num=2),
        _pr({"图号": "P001", "工序": 2, "换型时间(h)": 0.2, "单件工时(h)": float("inf")}, status=RowStatus.UPDATE, row_num=3),
        _pr({"图号": "P001", "工序": 3, "换型时间(h)": "abc", "单件工时(h)": "0.1"}, status=RowStatus.UPDATE, row_num=4),
    ]
    stats = svc.apply_preview_rows(preview_rows)
    assert int(stats.get("total_rows", 0)) == 3, stats
    assert int(stats.get("new_count", 0)) == 0, stats
    assert int(stats.get("update_count", 0)) == 0, stats
    assert int(stats.get("skip_count", 0)) == 0, stats
    assert int(stats.get("error_count", 0)) == 3, stats

    errors_sample = stats.get("errors_sample") or []
    assert len(errors_sample) >= 1


# ============================================================================
# part_operation_hours — mixed_rows（B 型，seed Part+PartOperation + monkeypatch 回滚）
# ============================================================================


def test_part_op_hours_apply_preview_rows_mixed_rows_commits_valid_and_keeps_row_errors(
    schema_conn,
) -> None:
    conn = schema_conn
    _seed_part_and_internal_op(conn)

    svc = PartOperationHoursExcelImportService(conn)
    preview_rows = [
        # 合法写库
        _pr({"图号": "P001", "工序": 1, "换型时间(h)": 2.0, "单件工时(h)": 1.0}, status=RowStatus.UPDATE, row_num=2),
        # 可解析，但业务错误（工序不存在）→ AppError → 行级错误，不应回滚合法行
        _pr({"图号": "P001", "工序": 999, "换型时间(h)": 0.2, "单件工时(h)": 0.1}, status=RowStatus.UPDATE, row_num=3),
        # 解析期错误
        _pr({"图号": "P001", "工序": 2, "换型时间(h)": float("nan"), "单件工时(h)": 0.1}, status=RowStatus.UPDATE, row_num=4),
    ]

    stats = svc.apply_preview_rows(preview_rows)

    assert int(stats.get("total_rows", 0)) == 3, stats
    assert int(stats.get("new_count", 0)) == 0, stats
    assert int(stats.get("update_count", 0)) == 1, stats
    assert int(stats.get("skip_count", 0)) == 0, stats
    assert int(stats.get("error_count", 0)) == 2, stats

    sh, uh = _get_hours(conn, part_no="P001", seq=1)
    assert sh == 2.0
    assert uh == 1.0


def test_part_op_hours_apply_preview_rows_unexpected_exception_rolls_back_all_changes(
    schema_conn, monkeypatch
) -> None:
    conn = schema_conn
    _seed_part_and_internal_op(conn)

    svc = PartOperationHoursExcelImportService(conn)
    sh0, uh0 = _get_hours(conn, part_no="P001", seq=1)

    orig = svc.part_svc.update_internal_hours
    calls = {"n": 0}

    def _wrapped(*args, **kwargs):
        calls["n"] += 1
        if int(calls["n"]) >= 2:
            raise RuntimeError("boom")
        return orig(*args, **kwargs)

    monkeypatch.setattr(svc.part_svc, "update_internal_hours", _wrapped)

    preview_rows = [
        _pr({"图号": "P001", "工序": 1, "换型时间(h)": 2.0, "单件工时(h)": 1.0}, status=RowStatus.UPDATE, row_num=2),
        _pr({"图号": "P001", "工序": 1, "换型时间(h)": 3.0, "单件工时(h)": 1.0}, status=RowStatus.UPDATE, row_num=3),
    ]

    with pytest.raises(RuntimeError):
        svc.apply_preview_rows(preview_rows)

    # 外层事务回滚：第一行的成功写入也应被撤销
    sh1, uh1 = _get_hours(conn, part_no="P001", seq=1)
    assert sh1 == sh0
    assert uh1 == uh0
