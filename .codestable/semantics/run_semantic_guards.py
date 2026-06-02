#!/usr/bin/env python
"""跑语义守卫(property + snapshot)。用隔离的 .venv-semantic(Python 3.14),不碰交付 .venv。

用法:
    python .codestable/semantics/run_semantic_guards.py            # 跑全部守卫
    APS_UPDATE_SEMANTIC_SNAPSHOTS=1 python .../run_semantic_guards.py  # 重建快照基线
深扫: HYPOTHESIS_PROFILE=semantic_deep python .../run_semantic_guards.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-semantic" / "bin" / "python"
TESTS = ROOT / ".codestable" / "semantics" / "tests"


def main() -> int:
    if not VENV_PY.exists():
        print(f"缺少隔离审计环境 {VENV_PY}。请先:", file=sys.stderr)
        print("  python3.14 -m venv .venv-semantic && "
              ".venv-semantic/bin/pip install hypothesis syrupy drift-analyzer", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env.setdefault("HYPOTHESIS_PROFILE", "semantic_fast")
    return subprocess.call(
        [str(VENV_PY), "-m", "pytest", str(TESTS), "-q", "-p", "no:cacheprovider"],
        env=env, cwd=str(ROOT),
    )


if __name__ == "__main__":
    raise SystemExit(main())
