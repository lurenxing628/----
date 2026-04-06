"""
回归测试：Excel 路由层不直接调用 *_no_tx（C02 收口）。
"""

from __future__ import annotations

import os
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_no_tx_hidden(path: Path) -> None:
    txt = path.read_text(encoding="utf-8")
    if "_no_tx(" in txt:
        raise RuntimeError(f"检测到路由层仍直接调用 *_no_tx：{path}")


def main() -> None:
    repo_root = Path(find_repo_root())
    targets = [
        repo_root / "web" / "routes" / "scheduler_excel_batches.py",
        repo_root / "web" / "routes" / "personnel_excel_operator_calendar.py",
    ]
    for p in targets:
        _assert_no_tx_hidden(p)
    print("OK")


if __name__ == "__main__":
    main()

