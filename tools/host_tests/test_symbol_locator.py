"""Host-only contracts for tools.symbol_locator; these tests do not enter the product gate.

走公开 CLI 入口（``python -m tools.symbol_locator``），夹具是只含一个产品函数的临时仓库。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from tools.symbol_locator.static_index import FUNCTIONS_FILE

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKUP_SCRIPTS = Path(".codestable", "checkup", "scripts")
# 夹具文件只在临时仓库里存在，拼出路径，不写成会被失效路径扫描器当成仓库路径的字面量。
SAMPLE_REL = "/".join(("core", "sample.py"))


def _fixture_repo(root: Path) -> Path:
    """临时仓库带上 symbol_locator 依赖的 tools 文件与调用图提取脚本：工具按 tools 包所在仓库定根。"""
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True)
    for name in ("__init__.py", "long_gate_paths.py"):
        shutil.copy2(REPO_ROOT / "tools" / name, tools_dir / name)
    shutil.copytree(
        REPO_ROOT / "tools" / "symbol_locator",
        tools_dir / "symbol_locator",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    scripts_dir = root / CHECKUP_SCRIPTS
    scripts_dir.mkdir(parents=True)
    for script in (REPO_ROOT / CHECKUP_SCRIPTS).glob("callgraph_*.py"):
        shutil.copy2(script, scripts_dir / script.name)
    sample = root / SAMPLE_REL
    sample.parent.mkdir()
    sample.write_text("def located_here():\n    return 1\n", encoding="utf-8")
    return root


def test_relative_callgraph_dir_is_read_where_the_rebuild_wrote_it(tmp_path):
    """仓库外运行且快照缺失需要重建时，相对 CHECKUP_CALLGRAPH 按调用方 cwd 解析一次，读与写落在同一目录。"""
    repo = _fixture_repo(tmp_path / "repo")
    outside = tmp_path / "outside"
    outside.mkdir()
    env = dict(
        os.environ,
        CHECKUP_CALLGRAPH="relative-callgraph",
        PYTHONPATH=str(repo),
        PYTHONDONTWRITEBYTECODE="1",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "tools.symbol_locator", "whereis", "located_here"],
        cwd=str(outside),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split(":", 1)[0] == SAMPLE_REL
    assert (outside / "relative-callgraph" / FUNCTIONS_FILE).is_file()
    assert not (repo / "relative-callgraph").exists()
