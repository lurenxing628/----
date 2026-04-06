from __future__ import annotations

import os
import re


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _assert_regex(text: str, pattern: str, msg: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE | re.DOTALL) is None:
        raise RuntimeError(msg + f"（pattern: {pattern}）")


def main() -> None:
    repo_root = _find_repo_root()
    css_path = os.path.join(repo_root, "static", "css", "ui_contract.css")
    css = _read(css_path)

    # 1) 全局兜底：所有表格单元格遇到超长 token 时可断词，避免跨列溢出
    _assert_regex(
        css,
        r"table\s+th\s*,\s*table\s+td\s*\{[^}]*overflow-wrap\s*:\s*anywhere\s*;",
        "ui_contract.css 缺少全局表格断词兜底（table th/td overflow-wrap:anywhere）",
    )

    # 2) 固定布局表格：强制单行 + 省略号，确保列表页列宽稳定、不串列
    _assert_regex(
        css,
        r"\.table-layout-fixed\s+th\s*,\s*\.table-layout-fixed\s+td\s*\{"
        r"[^}]*overflow\s*:\s*hidden\s*;"
        r"[^}]*text-overflow\s*:\s*ellipsis\s*;"
        r"[^}]*white-space\s*:\s*nowrap\s*;",
        "ui_contract.css 缺少 fixed 表格省略号契约（.table-layout-fixed th/td overflow hidden + ellipsis + nowrap）",
    )

    print("OK")


if __name__ == "__main__":
    main()

