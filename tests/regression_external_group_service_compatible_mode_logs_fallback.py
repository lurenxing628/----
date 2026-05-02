import os
import sqlite3
import sys
from unittest.mock import MagicMock


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    with open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process.external_group_service import ExternalGroupService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_schema(conn, repo_root)
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P001", "零件", "", "yes"),
        )
        for seq, op_type_name, ext_days in ((10, "表处理", 2.0), (20, "喷涂", 3.0), (30, "电镀", 4.0)):
            conn.execute(
                """
                INSERT INTO PartOperations (
                    part_no, seq, op_type_name, source, supplier_id, ext_days,
                    ext_group_id, setup_hours, unit_hours, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("P001", seq, op_type_name, "external", None, ext_days, "G001", 0.0, 0.0, "active"),
            )
        conn.execute(
            """
            INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("G001", "P001", 10, 30, "separate", None, None, None),
        )
        conn.commit()

        logger = MagicMock()
        svc = ExternalGroupService(conn, logger=logger)
        user_warnings = []
        svc.set_merge_mode(
            group_id="G001",
            merge_mode="separate",
            per_op_days={10: "", 20: "0", 30: "abc"},
            user_warnings=user_warnings,
            strict_mode=False,
        )

        rows = conn.execute(
            "SELECT seq, ext_days FROM PartOperations WHERE part_no=? AND ext_group_id=? ORDER BY seq",
            ("P001", "G001"),
        ).fetchall()
        assert len(rows) == 3, f"外部工序数量异常：{len(rows)}"
        for row in rows:
            assert abs(float(row["ext_days"] or 0.0) - 1.0) < 1e-9, f"兼容回退未按 1.0 天写入：{dict(row)!r}"

        warning_messages = [str(call.args[0]) for call in logger.warning.call_args_list if call.args]
        assert len(warning_messages) == 3, f"warning 次数异常：{warning_messages!r}"

        for seq in (10, 20, 30):
            matched = [msg for msg in warning_messages if f"外部工序 {seq}" in msg]
            assert matched, f"未找到 seq={seq} 的 fallback warning：{warning_messages!r}"
            msg = matched[0]
            assert "raw=" in msg, f"内部日志应保留原始输入便于诊断：{msg!r}"
            assert "ext_days" in msg, f"内部日志应保留目标字段便于诊断：{msg!r}"
            assert "compatible mode fallback" in msg, f"内部日志应保留兼容回退诊断：{msg!r}"

            user_matched = [text for text in user_warnings if f"外协工序 {seq}" in text]
            assert user_matched, f"未找到 seq={seq} 的用户提示：{user_warnings!r}"
            user_msg = user_matched[0]
            assert "raw=" not in user_msg, f"用户提示不应暴露原始输入：{user_msg!r}"
            assert "ext_days" not in user_msg, f"用户提示不应暴露内部字段：{user_msg!r}"
            assert "compatible mode" not in user_msg, f"用户提示不应暴露英文兼容模式：{user_msg!r}"
            assert "兼容模式" not in user_msg, f"用户提示不应使用偏技术的话：{user_msg!r}"
            assert "1.0 天回退" not in user_msg, f"用户提示不应使用偏技术的话：{user_msg!r}"
            assert "本次会先按 1 天记录" in user_msg, f"用户提示未说明处理方式：{user_msg!r}"
            assert "请尽快补成真实周期" in user_msg, f"用户提示未告诉用户下一步该补什么：{user_msg!r}"

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
