"""回归测试：打印介质契约——print.css 的 @media print 隐藏名单必须含 .sidebar
（2026-06-12 修复的存量缺陷：header/nav 元素级选择器盖不住 div.sidebar，
打印出 240px 深色占位列）+ @page A4 landscape 存在。文件级断言不起浏览器；
打印预览人工必查项清单见 roadmap drafts/anchor-baseline.md 第三节。"""

from __future__ import annotations

import re
from pathlib import Path

PRINT_CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "print.css"


def _read() -> str:
    return PRINT_CSS.read_text(encoding="utf-8")


def test_sidebar_in_print_hide_list():
    css = _read()
    hide_block = re.search(r"@media print\s*\{(.+?display:\s*none\s*!important;\s*\})", css, re.S)
    assert hide_block, "print.css 应有 @media print 内的 display:none 隐藏块"
    assert ".sidebar" in hide_block.group(1), (
        "打印隐藏名单必须含 .sidebar——它是 div（header/nav 元素选择器盖不住），"
        "缺了会打印出 240px 深色侧栏占位列"
    )


def test_page_rule_a4_landscape():
    css = _read()
    page_rule = re.search(r"@page\s*\{([^}]+)\}", css)
    assert page_rule, "print.css 应有 @page 规则"
    assert "A4 landscape" in page_rule.group(1)
