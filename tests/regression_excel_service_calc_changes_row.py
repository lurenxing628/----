import os
import sqlite3
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _DummyBackend:
    def read(self, *_args, **_kwargs):
        raise NotImplementedError

    def write(self, *_args, **_kwargs):
        raise NotImplementedError


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.excel_service import ExcelService, ImportMode, RowStatus

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        existing_row = conn.execute(
            'SELECT "OP001" AS "工号", "张三" AS "姓名", "active" AS "状态", 1 AS "数量", 1.0 AS "工时"'
        ).fetchone()
        assert existing_row is not None

        svc = ExcelService(backend=_DummyBackend(), logger=None, op_logger=None)
        preview = svc.preview_import(
            rows=[{"工号": "OP001", "姓名": "张三", "状态": "inactive", "数量": "1", "工时": "1"}],
            id_column="工号",
            existing_data={"OP001": existing_row},
            validators=None,
            mode=ImportMode.OVERWRITE,
        )
        assert len(preview) == 1
        pr = preview[0]
        assert pr.status == RowStatus.UPDATE, f"期望 UPDATE，实际={pr.status!r}"
        assert pr.changes.get("状态") == ("active", "inactive"), f"changes 异常：{pr.changes!r}"
        assert "数量" not in pr.changes and "工时" not in pr.changes, f"数值类型差异不应触发变更：{pr.changes!r}"

        preview2 = svc.preview_import(
            rows=[{"工号": "OP001", "姓名": "张三", "状态": "active", "数量": "1.0", "工时": 1}],
            id_column="工号",
            existing_data={"OP001": existing_row},
            validators=None,
            mode=ImportMode.OVERWRITE,
        )
        assert len(preview2) == 1
        pr2 = preview2[0]
        assert pr2.status == RowStatus.UNCHANGED, f"期望 UNCHANGED，实际={pr2.status!r}"
        assert not pr2.changes, f"不应有 changes：{pr2.changes!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

