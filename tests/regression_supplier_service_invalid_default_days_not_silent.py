import os
import sqlite3
import sys
from typing import List


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _Logger:
    def __init__(self) -> None:
        self.messages: List[str] = []

    def warning(self, message, *args, **kwargs) -> None:
        self.messages.append(str(message))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process.supplier_service import SupplierService

    schema_sql = open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8").read()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    logger = _Logger()
    try:
        conn.executescript(schema_sql)
        svc = SupplierService(conn, logger=logger, op_logger=None)

        created = svc.create("S_BAD", "坏默认周期供应商", default_days="abc", status="active")
        assert created.supplier_id == "S_BAD", f"供应商创建失败：{created!r}"
        row1 = conn.execute("SELECT default_days FROM Suppliers WHERE supplier_id=?", ("S_BAD",)).fetchone()
        assert row1 is not None, "供应商未落库"
        assert abs(float(row1["default_days"] or 0.0) - 1.0) < 1e-9, f"create fallback 默认周期异常：{row1['default_days']!r}"

        updated = svc.update("S_BAD", default_days="")
        assert updated.supplier_id == "S_BAD", f"供应商更新失败：{updated!r}"
        row2 = conn.execute("SELECT default_days FROM Suppliers WHERE supplier_id=?", ("S_BAD",)).fetchone()
        assert row2 is not None, "供应商更新后读取失败"
        assert abs(float(row2["default_days"] or 0.0) - 1.0) < 1e-9, f"update fallback 默认周期异常：{row2['default_days']!r}"

        messages = list(logger.messages)
        assert len(messages) >= 2, f"create/update fallback 未留痕：{messages!r}"
        assert all("默认周期输入无效" in msg for msg in messages[:2]), f"fallback 日志文案异常：{messages!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
