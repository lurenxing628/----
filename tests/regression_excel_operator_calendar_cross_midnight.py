from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any, Dict


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _assert_float_close(got: Any, expected: float, *, label: str) -> None:
    try:
        v = float(got)
    except Exception:
        raise AssertionError(f"{label}：期望可转为 float（期望值={expected}），实际={got!r}") from None
    if abs(v - float(expected)) > 1e-9:
        raise AssertionError(f"{label}：期望 {expected}，实际 {v}")


def _run_case(validate_row, row: Dict[str, Any], *, expected_hours: float) -> None:
    r = dict(row)
    err = validate_row(r)
    if err:
        raise AssertionError(f"预期校验通过，但返回错误：{err}；row={r!r}")
    _assert_float_close(r.get("可用工时"), expected_hours, label=f"可用工时({r.get('班次开始')}->{r.get('班次结束')})")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.excel_validators import get_operator_calendar_row_validate_and_normalize
    from data.repositories import OperatorRepository

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    try:
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)",
            ("OP001", "测试员工", "active", ""),
        )
        conn.commit()

        validate_row = get_operator_calendar_row_validate_and_normalize(
            conn,
            holiday_default_efficiency=0.8,
            op_repo=OperatorRepository(conn),
            inplace=True,
        )

        # Case A：跨午夜（22:00 -> 06:00）应视为次日结束，工时=8
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-01",
                "类型": "workday",
                "班次开始": "22:00",
                "班次结束": "06:00",
                # 故意给一个错误值，确保会被起止时间推导覆盖
                "可用工时": 1,
            },
            expected_hours=8.0,
        )

        # Case B：相等（08:00 -> 08:00）语义为 24h 班次（与 CalendarAdmin/Engine 一致）
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-02",
                "类型": "workday",
                "班次开始": "08:00",
                "班次结束": "08:00",
            },
            expected_hours=24.0,
        )

        # Case C：正常（08:00 -> 16:00）工时=8
        _run_case(
            validate_row,
            {
                "工号": "OP001",
                "日期": "2026-03-03",
                "类型": "workday",
                "班次开始": "08:00",
                "班次结束": "16:00",
                "可用工时": "0",
            },
            expected_hours=8.0,
        )

    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()

