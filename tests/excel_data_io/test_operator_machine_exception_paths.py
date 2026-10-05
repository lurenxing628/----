"""保留已登记的人员设备异常传播检查。"""

from __future__ import annotations

import os
import sqlite3
from unittest.mock import patch

import pytest

from core.errors import ValidationError
from core.services.common.excel_service import ImportPreviewRow, RowStatus
from core.services.personnel.operator_machine_service import OperatorMachineService
from tests._support.paths import REPO_ROOT_STR as REPO_ROOT

SCHEMA_PATH = os.path.join(REPO_ROOT, "schema.sql")


def _load_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _conn_with_links() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP1", "测试员"))
    conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC1", "设备"))
    conn.execute(
        "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        ("OP1", "MC1", "expert", "yes"),
    )
    conn.commit()
    return conn


def test_normalize_skill_level_optional_only_converts_value_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OperatorMachineService._normalize_skill_level_optional("unknown_level")

    assert "技能等级" in exc_info.value.message

    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=RuntimeError("normalize exploded"),
    ):
        with pytest.raises(RuntimeError, match="normalize exploded"):
            OperatorMachineService._normalize_skill_level_optional("expert")


def test_normalize_skill_level_stored_only_falls_back_for_value_error() -> None:
    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=ValueError("invalid skill"),
    ):
        assert OperatorMachineService._normalize_skill_level_stored("bad") == "normal"

    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=RuntimeError("normalize exploded"),
    ):
        with pytest.raises(RuntimeError, match="normalize exploded"):
            OperatorMachineService._normalize_skill_level_stored("expert")


def test_list_by_operator_propagates_unexpected_readside_normalization_errors() -> None:
    conn = _conn_with_links()
    try:
        svc = OperatorMachineService(conn)
        with patch(
            "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
            side_effect=RuntimeError("normalize exploded"),
        ):
            with pytest.raises(RuntimeError, match="normalize exploded"):
                svc.list_by_operator("OP1")
    finally:
        conn.close()


def test_resolve_write_values_only_converts_validation_error() -> None:
    conn = _conn_with_links()
    try:
        svc = OperatorMachineService(conn)
        preview_row = ImportPreviewRow(row_num=2, status=RowStatus.UPDATE, data={"技能等级": "unknown_level", "主操设备": "yes"}, message="")

        new_skill, new_primary, err = svc._resolve_write_values(
            preview_row,
            has_skill_col=True,
            has_primary_col=True,
            old={"skill_level": "normal", "is_primary": "no"},
        )
        assert new_skill == "normal"
        assert new_primary == "no"
        assert err is not None
        assert "技能等级" in err

        with patch(
            "core.services.personnel.operator_machine_normalizers.normalize_skill_level_optional",
            side_effect=RuntimeError("write exploded"),
        ):
            with pytest.raises(RuntimeError, match="write exploded"):
                svc._resolve_write_values(
                    ImportPreviewRow(row_num=3, status=RowStatus.UPDATE, data={"技能等级": "expert", "主操设备": "yes"}, message=""),
                    has_skill_col=True,
                    has_primary_col=True,
                    old={"skill_level": "normal", "is_primary": "no"},
                )
    finally:
        conn.close()
