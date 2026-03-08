from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from typing import Any


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _row_to_dict(row: Any) -> dict:
    if isinstance(row, sqlite3.Row):
        return {k: row[k] for k in row.keys()}
    if isinstance(row, dict):
        return dict(row)
    raise RuntimeError(f"不支持的 row 类型：{type(row)!r}")


def _expect_validation_error(fn, expected_text: str) -> None:
    from core.infrastructure.errors import ValidationError

    try:
        fn()
    except ValidationError as e:
        msg = getattr(e, "message", str(e))
        assert expected_text in msg, f"预期错误包含 {expected_text!r}，实际 {msg!r}"
        return
    raise RuntimeError(f"预期抛出 ValidationError：{expected_text}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import CalendarService

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_calendar_no_tx_hardening_")
    test_db = os.path.join(tmpdir, "aps_calendar_no_tx.db")
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.commit()

        cal_svc = CalendarService(conn, logger=None, op_logger=None)

        tx_global = cal_svc.upsert(
            "2026-03-10",
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="是",
            allow_urgent="是",
            remark="global tx",
        )
        no_tx_global = cal_svc.upsert_no_tx(
            {
                "date": "2026-03-11",
                "day_type": "工作日",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "是",
                "allow_urgent": "是",
                "remark": "global no_tx",
            }
        )
        row_global = conn.execute(
            "SELECT day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent FROM WorkCalendar WHERE date=?",
            ("2026-03-11",),
        ).fetchone()
        assert row_global is not None, "未写入 WorkCalendar.no_tx 记录"
        row_global_dict = _row_to_dict(row_global)
        assert row_global_dict["day_type"] == "workday", f"预期 no_tx.day_type=workday，实际 {row_global_dict['day_type']!r}"
        assert row_global_dict["allow_normal"] == "yes", f"预期 no_tx.allow_normal=yes，实际 {row_global_dict['allow_normal']!r}"
        assert row_global_dict["allow_urgent"] == "yes", f"预期 no_tx.allow_urgent=yes，实际 {row_global_dict['allow_urgent']!r}"
        assert no_tx_global.day_type == tx_global.day_type == "workday", "事务/非事务 day_type 不一致"
        assert no_tx_global.allow_normal == tx_global.allow_normal == "yes", "事务/非事务 allow_normal 不一致"
        assert no_tx_global.allow_urgent == tx_global.allow_urgent == "yes", "事务/非事务 allow_urgent 不一致"
        assert no_tx_global.shift_start == tx_global.shift_start == "08:00", "事务/非事务 shift_start 不一致"
        assert no_tx_global.shift_end == tx_global.shift_end == "16:00", "事务/非事务 shift_end 不一致"
        policy_tx_global = cal_svc.policy_for_datetime(datetime(2026, 3, 10, 9, 0, 0))
        policy_no_tx_global = cal_svc.policy_for_datetime(datetime(2026, 3, 11, 9, 0, 0))
        assert policy_tx_global.allow_normal == policy_no_tx_global.allow_normal == "yes", "全局日历 policy.allow_normal 不一致"
        assert policy_tx_global.is_priority_allowed("normal") is True, "事务路径 normal 应允许"
        assert policy_no_tx_global.is_priority_allowed("normal") is True, "no_tx 路径 normal 应允许"
        assert policy_tx_global.is_priority_allowed("urgent") is True, "事务路径 urgent 应允许"
        assert policy_no_tx_global.is_priority_allowed("urgent") is True, "no_tx 路径 urgent 应允许"

        tx_operator = cal_svc.upsert_operator_calendar(
            operator_id="OP100",
            date_value="2026-03-12",
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="是",
            allow_urgent="是",
            remark="operator tx",
        )
        no_tx_operator = cal_svc.upsert_operator_calendar_no_tx(
            {
                "operator_id": "OP100",
                "date": "2026-03-13",
                "day_type": "工作日",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "是",
                "allow_urgent": "是",
                "remark": "operator no_tx",
            }
        )
        row_operator = conn.execute(
            "SELECT day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-13"),
        ).fetchone()
        assert row_operator is not None, "未写入 OperatorCalendar.no_tx 记录"
        row_operator_dict = _row_to_dict(row_operator)
        assert row_operator_dict["day_type"] == "workday", f"预期 operator no_tx.day_type=workday，实际 {row_operator_dict['day_type']!r}"
        assert row_operator_dict["allow_normal"] == "yes", f"预期 operator no_tx.allow_normal=yes，实际 {row_operator_dict['allow_normal']!r}"
        assert row_operator_dict["allow_urgent"] == "yes", f"预期 operator no_tx.allow_urgent=yes，实际 {row_operator_dict['allow_urgent']!r}"
        assert no_tx_operator.day_type == tx_operator.day_type == "workday", "个人日历事务/非事务 day_type 不一致"
        assert no_tx_operator.allow_normal == tx_operator.allow_normal == "yes", "个人日历事务/非事务 allow_normal 不一致"
        assert no_tx_operator.allow_urgent == tx_operator.allow_urgent == "yes", "个人日历事务/非事务 allow_urgent 不一致"
        assert no_tx_operator.shift_start == tx_operator.shift_start == "08:00", "个人日历事务/非事务 shift_start 不一致"
        assert no_tx_operator.shift_end == tx_operator.shift_end == "16:00", "个人日历事务/非事务 shift_end 不一致"
        policy_tx_operator = cal_svc.policy_for_datetime(datetime(2026, 3, 12, 9, 0, 0), operator_id="OP100")
        policy_no_tx_operator = cal_svc.policy_for_datetime(datetime(2026, 3, 13, 9, 0, 0), operator_id="OP100")
        assert policy_tx_operator.allow_normal == policy_no_tx_operator.allow_normal == "yes", "个人日历 policy.allow_normal 不一致"
        assert policy_tx_operator.is_priority_allowed("normal") is True, "个人事务路径 normal 应允许"
        assert policy_no_tx_operator.is_priority_allowed("normal") is True, "个人 no_tx 路径 normal 应允许"
        assert policy_tx_operator.is_priority_allowed("urgent") is True, "个人事务路径 urgent 应允许"
        assert policy_no_tx_operator.is_priority_allowed("urgent") is True, "个人 no_tx 路径 urgent 应允许"

        _expect_validation_error(
            lambda: cal_svc.upsert_no_tx(
                {
                    "date": "2026-03-14",
                    "day_type": "workday",
                    "shift_hours": -1,
                    "efficiency": 1.0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "可用工时",
        )
        cnt_global_neg = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date=?", ("2026-03-14",)).fetchone()[0]
        assert int(cnt_global_neg) == 0, f"负工时 no_tx 不应落库，实际 count={cnt_global_neg}"

        _expect_validation_error(
            lambda: cal_svc.upsert_no_tx(
                {
                    "date": "2026-03-15",
                    "day_type": "workday",
                    "shift_hours": 8,
                    "efficiency": 0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "效率",
        )
        cnt_global_eff = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date=?", ("2026-03-15",)).fetchone()[0]
        assert int(cnt_global_eff) == 0, f"零效率 no_tx 不应落库，实际 count={cnt_global_eff}"

        _expect_validation_error(
            lambda: cal_svc.upsert_operator_calendar_no_tx(
                {
                    "operator_id": "OP100",
                    "date": "2026-03-16",
                    "day_type": "workday",
                    "shift_hours": -1,
                    "efficiency": 1.0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "可用工时",
        )
        cnt_operator_neg = conn.execute(
            "SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-16"),
        ).fetchone()[0]
        assert int(cnt_operator_neg) == 0, f"个人负工时 no_tx 不应落库，实际 count={cnt_operator_neg}"

        _expect_validation_error(
            lambda: cal_svc.upsert_operator_calendar_no_tx(
                {
                    "operator_id": "OP100",
                    "date": "2026-03-17",
                    "day_type": "workday",
                    "shift_hours": 8,
                    "efficiency": 0,
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                }
            ),
            "效率",
        )
        cnt_operator_eff = conn.execute(
            "SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP100", "2026-03-17"),
        ).fetchone()[0]
        assert int(cnt_operator_eff) == 0, f"个人零效率 no_tx 不应落库，实际 count={cnt_operator_eff}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
