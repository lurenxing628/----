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

        # REPLACE 语义：即使预览行为 UNCHANGED，清空后也必须重建该行，避免静默丢数。
        replace_calls = []
        replace_state = {"replace_called": 0}

        def _replace_existing_no_tx() -> None:
            replace_state["replace_called"] += 1

        replace_stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.REPLACE,
            preview_rows=[ImportPreviewRow(row_num=8, status=RowStatus.UNCHANGED, data={"id": "R1"}, message="unchanged in replace")],
            existing_row_ids={"R1"},
            replace_existing_no_tx=_replace_existing_no_tx,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=lambda pr, existed: replace_calls.append((_row_id_getter(pr), existed)),
            max_error_sample=10,
        )
        assert replace_state["replace_called"] == 1, replace_state
        assert replace_stats.error_count == 0, replace_stats
        assert replace_stats.skip_count == 0, replace_stats
        assert replace_stats.update_count == 0, replace_stats
        assert replace_stats.new_count == 1, replace_stats
        if replace_calls != [("R1", False)]:
            raise RuntimeError(f"REPLACE 下 UNCHANGED 行应重建写库，实际调用：{replace_calls!r}")

        # row_id_getter 异常兜底：即使 preview 行非 ERROR，row_id 为空也必须计入 error 并跳过写库。
        empty_calls = []
        empty_stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.OVERWRITE,
            preview_rows=[ImportPreviewRow(row_num=9, status=RowStatus.NEW, data={"id": ""}, message="empty id")],
            existing_row_ids=set(),
            replace_existing_no_tx=None,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=lambda pr, existed: empty_calls.append((_row_id_getter(pr), existed)),
            max_error_sample=10,
        )
        assert empty_stats.error_count == 1, empty_stats
        assert empty_stats.new_count == 0 and empty_stats.update_count == 0 and empty_stats.skip_count == 0, empty_stats
        assert empty_calls == [], empty_calls
        assert empty_stats.errors_sample and empty_stats.errors_sample[0].get("row") == 9, empty_stats.errors_sample

        # continue_on_app_error 语义：为 True 时按行降级计错继续；为 False 时遇到 AppError 直接中断
        from core.infrastructure.errors import ValidationError

        app_err_calls = []

        def _apply_row_maybe_error(pr, existed: bool) -> None:
            rid = _row_id_getter(pr)
            if rid == "E_APP":
                raise ValidationError("模拟导入错误", field="id")
            app_err_calls.append((rid, bool(existed)))

        cont_stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.OVERWRITE,
            preview_rows=[
                ImportPreviewRow(row_num=10, status=RowStatus.NEW, data={"id": "E_APP"}, message="app error"),
                ImportPreviewRow(row_num=11, status=RowStatus.NEW, data={"id": "OK1"}, message="ok row"),
            ],
            existing_row_ids=set(),
            replace_existing_no_tx=None,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_maybe_error,
            max_error_sample=10,
            continue_on_app_error=True,
        )
        assert cont_stats.error_count == 1 and cont_stats.new_count == 1, cont_stats
        assert app_err_calls == [("OK1", False)], app_err_calls
        assert cont_stats.errors_sample and cont_stats.errors_sample[0].get("row") == 10, cont_stats.errors_sample

        aborted = False
        try:
            execute_preview_rows_transactional(
                conn,
                mode=ImportMode.OVERWRITE,
                preview_rows=[ImportPreviewRow(row_num=12, status=RowStatus.NEW, data={"id": "E_APP"}, message="app error")],
                existing_row_ids=set(),
                replace_existing_no_tx=None,
                row_id_getter=_row_id_getter,
                apply_row_no_tx=_apply_row_maybe_error,
                max_error_sample=10,
                continue_on_app_error=False,
            )
        except ValidationError:
            aborted = True
        assert aborted is True, "continue_on_app_error=False 时应直接抛出 AppError"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

