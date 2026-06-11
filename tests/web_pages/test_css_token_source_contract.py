"""守卫测试（QUALITY_GATE_GUARD_TESTS 登记）：设计令牌唯一真相源契约——
00-tokens.css 含定版四色且暗色块非 token 行 ≤10（roadmap 4.4 红线）；
其余 CSS 文件裸 hex 计数冻结白名单只许降不许升（00-tokens 之外新增裸 hex
由本测试拒绝，hex-migration 逐文件清零时同步下调字典）；负荷阈值 Python
单点（workbench 与 cards 引用同一常量、全仓唯一定义）。"""

from __future__ import annotations

import re
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parents[2] / "static" / "css"

# 裸 hex：3/4/6/8 位全收（alpha 变体不漏）；\b 边界挡 #id 选择器后跟字母的形态
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

# 冻结白名单（2026-06-12 实测初值）：per-file 上限，只许降不许升；
# 新 CSS 文件不在表内 = 上限 0。hex-migration 清零一个文件就下调一行。
HEX_FREEZE_ALLOWANCE = {
    "00-tokens.css": None,  # 唯一真相源，不设限
    "ui_contract.css": 294,
    "style.css": 72,
    "aps_gantt.css": 115,
    "calendar_picker.css": 33,
    "frappe-gantt.css": 25,
    "aps_gantt_simulation.css": 16,
    "print.css": 5,
    "compatibility.css": 4,
    "resource_dispatch.css": 0,
}

DEFINITIVE_COLORS = {
    "--ui-success: #16a34a",
    "--ui-warning: #d97706",
    "--ui-danger: #dc2626",
    "--ui-primary: #2563eb",
}

# 非颜色 token 坍缩值锚：回退链坍缩必须取旧运行时实际值（链首 style.css 的定义），
# 不是 ui_contract 的 fallback 一层值——实现审核曾抓到 shadow-md 坍缩错
COLLAPSED_VALUE_ANCHORS = {
    "--ui-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
    "--ui-radius: 6px",
}


def _strip_comments(css: str) -> str:
    # 状态机不必：CSS 注释无嵌套，非贪婪整文件正则即等价剥离（含多行块注释）
    return _COMMENT_RE.sub("", css)


def _count_bare_hex(css_path: Path) -> int:
    return len(_HEX_RE.findall(_strip_comments(css_path.read_text(encoding="utf-8"))))


def test_tokens_file_declares_definitive_colors():
    css = _strip_comments((CSS_DIR / "00-tokens.css").read_text(encoding="utf-8"))
    for decl in DEFINITIVE_COLORS:
        assert decl in css, f"00-tokens.css 缺定版声明 {decl}"
    for decl in COLLAPSED_VALUE_ANCHORS:
        assert decl in css, f"00-tokens.css 坍缩值漂移：{decl}"


def test_tokens_dark_block_is_pure_token_reassignment():
    css = _strip_comments((CSS_DIR / "00-tokens.css").read_text(encoding="utf-8"))
    m = re.search(r'html\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S)
    assert m, "00-tokens.css 应有暗色块"
    offenders = [
        line.strip()
        for line in m.group(1).splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    assert len(offenders) <= 10, f"暗色块非 token 行超红线（≤10）：{offenders}"
    assert not offenders, f"初版暗色块应为纯 token 重赋值（现 {offenders}）"


def test_bare_hex_frozen_outside_tokens_file():
    findings = []
    for css_path in sorted(CSS_DIR.glob("*.css")):
        allowance = HEX_FREEZE_ALLOWANCE.get(css_path.name, 0)
        if allowance is None:
            continue
        count = _count_bare_hex(css_path)
        if count > allowance:
            findings.append(f"{css_path.name}: {count} > 冻结上限 {allowance}")
    assert not findings, (
        "00-tokens.css 之外新增裸 hex 被拒绝（roadmap 4.4 白名单契约）。\n"
        "新增颜色请定义 token 或消费既有 var(--ui-*)；若是 hex-migration 清债后"
        "需要下调上限，请同步改 HEX_FREEZE_ALLOWANCE：\n  " + "\n  ".join(findings)
    )


def test_load_ratio_single_source():
    from web.viewmodels import dashboard_workbench, dashboard_workbench_cards

    assert dashboard_workbench.LOAD_WARNING_RATIO is dashboard_workbench_cards.LOAD_WARNING_RATIO
    assert dashboard_workbench.LOAD_DANGER_RATIO is dashboard_workbench_cards.LOAD_DANGER_RATIO
    assert dashboard_workbench_cards.LOAD_WARNING_RATIO == 0.75
    assert dashboard_workbench_cards.LOAD_DANGER_RATIO == 0.90

    # 唯一定义点：viewmodels 下不允许第二处负荷阈值字面量定义
    viewmodels = Path(__file__).resolve().parents[2] / "web" / "viewmodels"
    defining_files = [
        py.name
        for py in viewmodels.glob("*.py")
        if re.search(r"^LOAD_WARNING_RATIO\s*=", py.read_text(encoding="utf-8"), re.M)
    ]
    assert defining_files == ["dashboard_workbench_cards.py"], defining_files
