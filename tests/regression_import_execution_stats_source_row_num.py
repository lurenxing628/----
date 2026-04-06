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

    from core.infrastructure.errors import ValidationError
    from core.services.common.excel_import_executor import execute_preview_rows_transactional
    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus

    conn = sqlite3.connect(":memory:")
    try:
        preview_rows = [
            ImportPreviewRow(
                row_num=2,
                source_row_num=9,
                source_sheet_name="SheetA",
                status=RowStatus.ERROR,
                data={"id": "E1"},
                message="预览阶段错误",
            ),
            ImportPreviewRow(
                row_num=3,
                source_row_num=11,
                source_sheet_name="SheetA",
                status=RowStatus.NEW,
                data={"id": ""},
                message="缺少主键",
            ),
            ImportPreviewRow(
                row_num=4,
                source_row_num=15,
                source_sheet_name="SheetA",
                status=RowStatus.NEW,
                data={"id": "APP_ERR"},
                message="应用阶段错误",
            ),
            ImportPreviewRow(
                row_num=5,
                source_row_num=20,
                source_sheet_name="SheetA",
                status=RowStatus.NEW,
                data={"id": "OK1"},
                message="正常写入",
            ),
        ]

        apply_calls = []

        def _row_id_getter(pr) -> str:
            return str((pr.data or {}).get("id") or "").strip()

        def _apply_row_no_tx(pr, existed: bool) -> None:
            rid = _row_id_getter(pr)
            if rid == "APP_ERR":
                raise ValidationError("应用阶段失败", field="id")
            apply_calls.append((rid, bool(existed)))

        stats = execute_preview_rows_transactional(
            conn,
            mode=ImportMode.OVERWRITE,
            preview_rows=preview_rows,
            existing_row_ids=set(),
            replace_existing_no_tx=None,
            row_id_getter=_row_id_getter,
            apply_row_no_tx=_apply_row_no_tx,
            max_error_sample=10,
            continue_on_app_error=True,
        )

        if stats.error_count != 3 or stats.new_count != 1 or stats.update_count != 0 or stats.skip_count != 0:
            raise RuntimeError(f"执行器统计异常：{stats!r}")
        if apply_calls != [("OK1", False)]:
            raise RuntimeError(f"执行器写库调用异常：{apply_calls!r}")

        errors_sample = list(stats.errors_sample or [])
        if [item.get("row") for item in errors_sample] != [9, 11, 15]:
            raise RuntimeError(f"执行器错误样本 row 未优先使用 source_row_num：{errors_sample!r}")
        if [item.get("source_row_num") for item in errors_sample] != [9, 11, 15]:
            raise RuntimeError(f"执行器错误样本 source_row_num 异常：{errors_sample!r}")
        if any(item.get("source_sheet_name") != "SheetA" for item in errors_sample):
            raise RuntimeError(f"执行器错误样本 source_sheet_name 异常：{errors_sample!r}")
        if errors_sample[0].get("message") != "预览阶段错误":
            raise RuntimeError(f"执行器未保留预览阶段错误文案：{errors_sample!r}")
        if errors_sample[1].get("message") != "缺少主键，无法写入。":
            raise RuntimeError(f"执行器未为缺少主键使用统一错误文案：{errors_sample!r}")
        if errors_sample[2].get("message") != "应用阶段失败":
            raise RuntimeError(f"执行器未保留应用阶段错误文案：{errors_sample!r}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
