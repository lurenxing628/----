import os
import sqlite3
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.excel_import_executor import execute_preview_rows_transactional
    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus

    conn = sqlite3.connect(":memory:")
    try:
        apply_calls = []
        existing_row_ids = {"A1", "S1", "U1"}
        preview_rows = [
            ImportPreviewRow(row_num=2, status=RowStatus.ERROR, data={"id": "E1"}, message="bad row"),
            ImportPreviewRow(row_num=3, status=RowStatus.SKIP, data={"id": "S1"}, message="skip row"),
            ImportPreviewRow(row_num=4, status=RowStatus.UNCHANGED, data={"id": "U1"}, message="unchanged row"),
            ImportPreviewRow(row_num=5, status=RowStatus.UPDATE, data={"id": "A1"}, message="update row"),
            ImportPreviewRow(row_num=6, status=RowStatus.NEW, data={"id": "N1"}, message="new row"),
        ]

        def _row_id_getter(pr) -> str:
            return str(pr.data.get("id") or "").strip()

        def _apply_row_no_tx(pr, existed: bool) -> None:
            apply_calls.append((_row_id_getter(pr), bool(existed)))

        stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.OVERWRITE,
            preview_rows=preview_rows,
            existing_row_ids=existing_row_ids,
            replace_existing_no_tx=None,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_no_tx,
            max_error_sample=10,
        )

        assert stats.error_count == 1, stats
        assert stats.skip_count == 1, stats
        assert stats.update_count == 1, stats
        assert stats.new_count == 1, stats
        assert len(stats.errors_sample) == 1 and stats.errors_sample[0]["row"] == 2, stats.errors_sample

        wrote_ids = {rid for rid, _ in apply_calls}
        if wrote_ids != {"A1", "N1"}:
            raise RuntimeError(f"执行器写入行异常：{wrote_ids!r}")
        existed_map = {rid: existed for rid, existed in apply_calls}
        if existed_map.get("A1") is not True or existed_map.get("N1") is not False:
            raise RuntimeError(f"执行器 existed 判定异常：{existed_map!r}")

        # APPEND 兜底语义：即使调用方未标注 SKIP，existing_row_ids 命中也应被跳过。
        append_calls = []
        append_stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.APPEND,
            preview_rows=[ImportPreviewRow(row_num=7, status=RowStatus.UPDATE, data={"id": "EX1"}, message="existing in append")],
            existing_row_ids={"EX1"},
            replace_existing_no_tx=None,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=lambda pr, existed: append_calls.append((_row_id_getter(pr), existed)),
            max_error_sample=10,
        )
        assert append_stats.skip_count == 1, append_stats
        assert append_stats.new_count == 0 and append_stats.update_count == 0, append_stats
        if append_calls:
            raise RuntimeError(f"APPEND 兜底不应写库，实际调用：{append_calls!r}")

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

