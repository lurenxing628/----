import os
import sqlite3
import sys
from types import SimpleNamespace


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

    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
    from core.services.scheduler import BatchService

    conn = sqlite3.connect(":memory:")
    try:
        svc = BatchService(conn)
        calls = {"replace": 0, "update": 0, "create": 0, "rebuild": 0}

        def _replace_no_tx() -> None:
            calls["replace"] += 1

        def _update_no_tx(*_args, **_kwargs) -> None:
            calls["update"] += 1
            raise RuntimeError("UNCHANGED 行不应触发 update_no_tx")

        def _create_no_tx(*_args, **_kwargs) -> None:
            calls["create"] += 1
            raise RuntimeError("UNCHANGED 行不应触发 create_no_tx")

        def _create_batch_from_template_no_tx(*_args, **_kwargs) -> None:
            calls["rebuild"] += 1
            raise RuntimeError("UNCHANGED 行不应触发 create_batch_from_template_no_tx(rebuild_ops=True)")

        svc.delete_all_no_tx = _replace_no_tx  # type: ignore[assignment]
        svc.update_no_tx = _update_no_tx  # type: ignore[assignment]
        svc.create_no_tx = _create_no_tx  # type: ignore[assignment]
        svc.create_batch_from_template_no_tx = _create_batch_from_template_no_tx  # type: ignore[assignment]

        preview_rows = [
            ImportPreviewRow(
                row_num=2,
                status=RowStatus.UNCHANGED,
                data={
                    "批次号": "B001",
                    "图号": "P001",
                    "数量": 10,
                    "交期": "2026-01-25",
                    "优先级": "normal",
                    "齐套": "yes",
                    "齐套日期": "2026-01-24",
                    "备注": "unchanged-row",
                },
                message="无变更",
            )
        ]

        result = svc.import_from_preview_rows(
            preview_rows=preview_rows,
            mode=ImportMode.OVERWRITE,
            parts_cache={"P001": SimpleNamespace(part_name="测试零件")},
            auto_generate_ops=True,
            existing_ids={"B001"},
        )

        assert int(result.get("total_rows", 0)) == 1, result
        assert int(result.get("new_count", 0)) == 0, result
        assert int(result.get("update_count", 0)) == 0, result
        assert int(result.get("skip_count", 0)) == 1, result
        assert int(result.get("error_count", 0)) == 0, result
        assert (
            int(result.get("new_count", 0))
            + int(result.get("update_count", 0))
            + int(result.get("skip_count", 0))
            + int(result.get("error_count", 0))
            == int(result.get("total_rows", 0))
        ), result
        assert bool(result.get("auto_generate_ops")) is True, result

        if any(v != 0 for v in calls.values()):
            raise RuntimeError(f"UNCHANGED 行触发了不应执行的写入/重建调用：{calls!r}")

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

