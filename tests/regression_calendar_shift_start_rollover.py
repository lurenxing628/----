import os
import sys
import sqlite3
from datetime import datetime, date


def find_repo_root() -> str:
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    """
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler import CalendarService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    # 两天的工作日历：Day1 08:00 开始，Day2 07:00 开始
    day1 = date(2026, 1, 1).isoformat()
    day2 = date(2026, 1, 2).isoformat()
    conn.execute(
        """
        INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (day1, "workday", "08:00", "16:00", 8.0, 1.0, "yes", "yes", "regression"),
    )
    conn.execute(
        """
        INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (day2, "workday", "07:00", "15:00", 8.0, 1.0, "yes", "yes", "regression"),
    )
    conn.commit()

    cal = CalendarService(conn)

    # 1) adjust_to_working_time：跨天时不应沿用“当天 shift_start”，否则会错过下一天更早的 07:00
    dt_after_shift = datetime(2026, 1, 1, 18, 0, 0)
    adjusted = cal.adjust_to_working_time(dt_after_shift, priority="normal")
    assert adjusted == datetime(2026, 1, 2, 7, 0, 0), f"adjust_to_working_time 跨天错误：{adjusted!r}"

    # 2) add_working_hours：跨天推进应从下一天 07:00 开始（结果应比旧实现提前 1 小时）
    start = datetime(2026, 1, 1, 15, 0, 0)
    end = cal.add_working_hours(start, 2.0, priority="normal")
    assert end == datetime(2026, 1, 2, 8, 0, 0), f"add_working_hours 跨天错误：{end!r}"

    print("OK")


if __name__ == "__main__":
    main()

