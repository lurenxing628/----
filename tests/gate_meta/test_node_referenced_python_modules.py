"""回归测试：浏览器探针的 .cjs 脚本用子进程拉起的 Python 模块，必须还在盘上。

为什么需要这条：tests/workbench 下有 260 个 .cjs 探针，它们用 spawn 起
`.venv/bin/python -m tests.workbench.<模块>` 或 `python -B <路径>.py` 来准备后端。
这条调用边在 Python 侧完全不可见——grep .py/.md/.json/.yml/.toml/.iss/.bat/.spec 全都搜不到，
import 图、符号索引、死代码扫描也都看不见。

2026-09-21 就这么删错过两个：`field_workspace_probe_server.py`（4 处 .cjs 引用）和
`final_planning_database_probe.py`（2 处），当时按"全仓库零引用"判定删掉，浏览器车道实跑才
报出 `No module named tests.workbench.field_workspace_probe_server`。而那条车道当时一个多
小时才跑一次、且长期没人跑，所以静态判定错了三天都不会有人知道。

这条测试几毫秒就跑完，不需要 Node 也不需要浏览器。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Set

from tests._support.paths import REPO_ROOT

SCRIPT_ROOT = REPO_ROOT / "tests"
# spawn(..., ['-m', 'tests.workbench.field_workspace_probe_server', ...])
_DASH_M = re.compile(r"""['"]-m['"]\s*,\s*['"](tests(?:\.[A-Za-z_][\w]*)+)['"]""")
# path.join(__dirname, 'final_planning_database_probe.py')
_SIBLING_PY = re.compile(r"""__dirname\s*,\s*['"]([\w./-]+\.py)['"]""")


def _node_scripts() -> List[Path]:
    return sorted(path for pattern in ("*.cjs", "*.js", "*.mjs")
                  for path in SCRIPT_ROOT.rglob(pattern) if "__pycache__" not in path.parts)


def _missing_targets() -> Dict[str, Set[str]]:
    """返回 {缺失的目标: {引用它的脚本}}。"""
    missing: Dict[str, Set[str]] = {}
    for script in _node_scripts():
        text = script.read_text(encoding="utf-8", errors="replace")
        referrer = str(script.relative_to(REPO_ROOT))
        for module in _DASH_M.findall(text):
            base = REPO_ROOT / Path(*module.split("."))
            if not (base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()):
                missing.setdefault(f"python -m {module}", set()).add(referrer)
        for name in _SIBLING_PY.findall(text):
            if not (script.parent / name).is_file():
                missing.setdefault(str((script.parent / name).relative_to(REPO_ROOT)), set()).add(referrer)
    return missing


def test_node_probes_do_not_reference_deleted_python_modules() -> None:
    missing = _missing_targets()
    assert not missing, "浏览器探针要起的 Python 模块不在盘上（删之前先搜 .cjs）：\n" + "\n".join(
        f"  {target}  ← {', '.join(sorted(referrers))}" for target, referrers in sorted(missing.items()))


def test_the_scan_actually_reaches_the_probe_scripts() -> None:
    """扫描范围塌成空集时上面那条会假绿，这里钉住它确实看到了探针。"""
    scripts = _node_scripts()
    assert len(scripts) > 100, f"只扫到 {len(scripts)} 个 Node 探针，扫描范围可能塌了"
    joined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in scripts)
    assert _DASH_M.search(joined), "没有匹配到任何 python -m 调用，正则可能已经失配"
    assert _SIBLING_PY.search(joined), "没有匹配到任何同目录 .py 调用，正则可能已经失配"
