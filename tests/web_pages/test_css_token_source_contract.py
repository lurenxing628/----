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

# 已被定版色取代的旧语义色（success/warning/danger 分叉前的值）。守卫只数数量
# 会让它们从旁路回潮（finding-09）：这里按 per-file 冻结实际出现次数，只许降不许升，
# 且不在表内的文件出现任一退役值即拒绝——回潮时能看到「哪个值在哪个文件冒出来」。
# hex-migration（#6）逐处清零时同步下调；清零后从表里删行。
RETIRED_SEMANTIC_HEX = ("#10b981", "#f59e0b", "#ef4444")
RETIRED_HEX_FREEZE = {
    "aps_gantt.css": {"#f59e0b": 1, "#ef4444": 2},
    "ui_contract.css": {"#10b981": 1, "#f59e0b": 1},
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


def _count_retired_hex(css_text: str, retired_hex: str) -> int:
    # 退役色是 6 位 hex，可能以 8 位 alpha 变体出现（#10b981ff 等 Tailwind 半透明写法）——
    # 裸 `re.escape(hx)+\b` 对 8 位变体漏检（6 位末位与 alpha 字符间无词边界）。改按 hex token
    # 整体比对：6 位精确等于退役值、或 8 位前 6 位等于退役值，都算回潮。
    target = retired_hex.lower().lstrip("#")
    hits = 0
    for token in _HEX_RE.findall(css_text):
        t = token.lower().lstrip("#")
        if t == target or (len(t) == 8 and t[:6] == target):
            hits += 1
    return hits


def test_tokens_file_declares_definitive_colors():
    css = _strip_comments((CSS_DIR / "00-tokens.css").read_text(encoding="utf-8"))
    # 亮色态文本 = 去掉暗色块后的部分（锚守卫只对 light root 生效）
    light_css = re.sub(r'html\[data-theme="dark"\]\s*\{.*?\}', "", css, flags=re.S)
    for decl in DEFINITIVE_COLORS | COLLAPSED_VALUE_ANCHORS:
        name = decl.split(":")[0]
        declared = re.findall(rf"{re.escape(name)}\s*:[^;]+;", light_css)
        # 同名声明必须唯一且逐字等于锚——后写第二个同名错误值也会被抓
        assert len(declared) == 1, f"{name} 在 light root 应唯一声明（现 {declared}）"
        assert declared[0].rstrip(";").replace(" :", ":") == decl, (
            f"00-tokens.css 值漂移：{declared[0]} != {decl};"
        )


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
    # 暗色块禁止出现已被定版色取代的旧语义色（form 守卫只看行是否以 -- 开头，挡不住
    # 旧值回潮——finding-09）：暗色 token 的值也必须是定版/暗色族色，不得退回旧语义色。
    dark_retired = [hx for hx in RETIRED_SEMANTIC_HEX if _count_retired_hex(m.group(1), hx)]
    assert not dark_retired, f"暗色块出现已退役旧语义色（应用定版色/暗色族）：{dark_retired}"


def test_retired_semantic_hex_frozen_only_decreases():
    # 旧语义色 per-file 冻结：只许降不许升，且不在冻结表内的文件出现任一退役值即拒绝。
    findings = []
    for css_path in sorted(CSS_DIR.glob("*.css")):
        body = _strip_comments(css_path.read_text(encoding="utf-8"))
        allowed = RETIRED_HEX_FREEZE.get(css_path.name, {})
        for hx in RETIRED_SEMANTIC_HEX:
            count = _count_retired_hex(body, hx)
            ceiling = allowed.get(hx, 0)
            if count > ceiling:
                findings.append(f"{css_path.name}: {hx} 出现 {count} 次 > 冻结上限 {ceiling}")
    assert not findings, (
        "已退役旧语义色回潮被拒绝（定版色见 DEFINITIVE_COLORS）。新增颜色请用 var(--ui-*)；"
        "若是 hex-migration 清债后下调，请同步改 RETIRED_HEX_FREEZE：\n  " + "\n  ".join(findings)
    )


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


def test_count_retired_hex_helper_detects_six_and_eight_digit():
    # 直接钉死 _count_retired_hex 逻辑（不依赖生产 CSS 恰好有样本）：6 位精确 + 8 位 alpha
    # 变体都计入、定版色与别的退役色不误判。作为回归锚点——防止未来 helper 被改回旧的
    # `re.escape(hx)+\b` 写法（对 8 位变体漏检）时，现有生产 CSS 无样本而静默漏过（Codex 建议）。
    assert _count_retired_hex("a{color:#10b981}", "#10b981") == 1
    assert _count_retired_hex("a{color:#10b981ff}", "#10b981") == 1  # 8 位 alpha 变体
    assert _count_retired_hex("a{color:#10b981} b{color:#10b981cc}", "#10b981") == 2
    assert _count_retired_hex("a{color:#16a34a}", "#10b981") == 0  # 定版色不误判
    assert _count_retired_hex("a{color:#ef4444}", "#10b981") == 0  # 别的退役色不串记


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
