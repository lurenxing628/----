"""Win7 离线交付契约：onedir 打包脚本必须声明 networkx 隐藏导入，且 win7-lite 依赖锁定 networkx==3.1。

对应 2026-06-17 深审 finding-22：默认 graph_analysis_mode=on 需要 NetworkX，
本测试钉住打包脚本与依赖清单口径，防止离线包再次漏掉图分析依赖。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_win7_onedir_build_declares_networkx_hidden_import() -> None:
    script = (REPO_ROOT / "build_win7_onedir.bat").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "requirements-optimizer-lite-win7.txt").read_text(encoding="utf-8")

    assert script.count("--hidden-import networkx") == 2
    assert "networkx==3.1" in requirements
