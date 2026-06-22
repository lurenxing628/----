#!/usr/bin/env python
"""跑 drift-analyzer 结构腐蚀扫描,写 evidence/SemanticDebt/drift/。只读、不改代码、不直接 fail。

用 .venv-semantic(Python 3.14)。drift exit code: 0/1 都属正常(1=有 findings)。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 走 `python -m drift` 而非 .venv-semantic/bin/drift 控制台脚本：后者 shebang 写死绝对路径,
# 仓库整体搬迁(如 ~/Documents → ~/GitHub)后会 FileNotFoundError 静默失效;模块入口对搬迁免疫。
VENV_PY = ROOT / ".venv-semantic" / "bin" / "python"
OUT = ROOT / "evidence" / "SemanticDebt" / "drift"


def main() -> int:
    if not VENV_PY.exists():
        print(f"缺少隔离审计环境 {VENV_PY}。先建 .venv-semantic 并装 drift-analyzer。", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "drift-baseline.json"
    md_path = OUT / "drift-baseline.md"
    rc = subprocess.call(
        [str(VENV_PY), "-m", "drift", "analyze", "--repo", ".", "--format", "json",
         "--progress", "none", "-o", str(json_path)],
        cwd=str(ROOT),
    )
    if rc not in (0, 1):
        return rc
    with md_path.open("w", encoding="utf-8") as fh:
        subprocess.call(
            [str(VENV_PY), "-m", "drift", "analyze", "--repo", ".", "--format", "markdown", "--progress", "none"],
            cwd=str(ROOT), stdout=fh,
        )
    print(f"wrote {json_path} + {md_path}")
    print("下一步: 重生成 agent brief 见 .codestable/semantics/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
