"""
回归测试：禁止在 HTML inline event handler（onclick/onsubmit/...）中直接插入 Jinja 变量。

背景：
- 在形如 onsubmit="return confirm('...{{ var }}...')" 的场景里，Jinja2 的 HTML 转义（&#39; 等）
  会在浏览器解析属性值时被解码回引号，从而打破 JS 字符串边界，引发 XSS / JS 注入。

策略：
- 扫描 templates/ 与 web_new_test/templates/ 内的 *.html
- 若发现 on*="...{{ ... }}" 或 on*='...{{ ... }}' 这种模式：直接失败

注意：本测试只针对“inline 事件属性 + Jinja 插值”这一高风险组合；
      on* 属性里不含 {{ }} 的纯静态字符串不在本测试范围内。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def iter_template_files(repo_root: str) -> List[str]:
    roots = [
        os.path.join(repo_root, "templates"),
        os.path.join(repo_root, "web_new_test", "templates"),
    ]
    out: List[str] = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        for dirpath, _dirnames, filenames in os.walk(r):
            for fn in filenames:
                if not fn.lower().endswith(".html"):
                    continue
                out.append(os.path.join(dirpath, fn))
    out.sort()
    return out


def scan_inline_event_jinja(repo_root: str) -> List[Tuple[str, int, str]]:
    # 仅匹配 HTML attribute 形态：空白 + onXxx= + 引号 + ...{{...}}
    pat_dq = re.compile(r'\son[a-zA-Z]+\s*=\s*"[^"]*\{\{')
    pat_sq = re.compile(r"\son[a-zA-Z]+\s*=\s*'[^']*\{\{")

    hits: List[Tuple[str, int, str]] = []
    for fpath in iter_template_files(repo_root):
        rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
        try:
            txt = Path(fpath).read_text(encoding="utf-8", errors="strict")
        except Exception:
            txt = Path(fpath).read_text(encoding="utf-8", errors="ignore")

        for i, line in enumerate(txt.splitlines(), start=1):
            # 粗过滤：降低在纯 JS/文本里误报的概率
            if "<" not in line:
                continue
            if pat_dq.search(line) or pat_sq.search(line):
                hits.append((rel, i, line.strip()))
    return hits


def main() -> None:
    repo_root = find_repo_root()
    hits = scan_inline_event_jinja(repo_root)
    if hits:
        print("[FAIL] 检测到 inline on* 事件属性中包含 Jinja 插值（存在 XSS/注入风险）：")
        for rel, ln, src in hits[:50]:
            print(f"  - {rel}:{ln}: {src}")
        if len(hits) > 50:
            print(f"  ... (+{len(hits) - 50})")
        raise SystemExit(1)
    print("OK: no inline event handlers contain Jinja interpolation.")


if __name__ == "__main__":
    main()

