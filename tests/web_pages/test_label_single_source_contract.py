"""守卫测试（QUALITY_GATE_GUARD_TESTS 登记）：排产词表唯一字源契约——
9 个收编模板禁回潮内联 strategy_zh/status_zh 字面字典（analysis.html 的后端注入
形态豁免）；'ok2' 死键在 templates/web 零现身（写入方零证据，重新引入即语义漂移）；
真源派生：analysis_overview/guardrail_messages 不得再手写 status 字典。"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RECLAIMED_TEMPLATES = (
    "templates/dashboard.html",
    "templates/scheduler/gantt.html",
    "templates/scheduler/resource_dispatch.html",
    "templates/scheduler/week_plan.html",
    "templates/reports/index.html",
    "templates/reports/overdue.html",
    "templates/reports/utilization.html",
    "templates/reports/execution_review.html",
    "templates/reports/downtime.html",
)

# 字面字典回潮形态：{% set status_zh = {...} %}（analysis.html 的
# {% set status_zh = analysis_labels.get(...) %} 是后端注入，不命中本正则）
_INLINE_DICT_RE = re.compile(r"\{%\s*set\s+(?:status_zh|strategy_zh)\s*=\s*\{")


def test_no_inline_label_dict_in_reclaimed_templates():
    offenders = []
    for rel in RECLAIMED_TEMPLATES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if _INLINE_DICT_RE.search(text):
            offenders.append(rel)
    assert not offenders, f"模板内联词表回潮（唯一字源在 viewmodel decorate 链）：{offenders}"


def test_ok2_dead_key_never_returns():
    offenders = []
    for base in ("templates", "web"):
        for path in (REPO_ROOT / base).rglob("*"):
            if path.suffix not in (".py", ".html"):
                continue
            text = path.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                # 注释里的死键考古说明豁免（result_state 的拍板留证）
                if "ok2" in line and not line.lstrip().startswith("#"):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}")
    assert not offenders, f"'ok2' 死键回潮（写入方零证据，合法值见 ScheduleResultStatus）：{offenders}"


def test_python_label_dicts_derive_from_single_source():
    overview = (REPO_ROOT / "web/viewmodels/scheduler_analysis_overview.py").read_text(encoding="utf-8")
    guardrail = (REPO_ROOT / "web/viewmodels/scheduler_plan_guardrail_messages.py").read_text(encoding="utf-8")
    for text, name in ((overview, "analysis_overview"), (guardrail, "guardrail_messages")):
        assert "result_status_display_labels" in text, f"{name} 应从真源派生 status 字典"
        # 禁手写 status 展示字典（"success": "成功" 字面对出现即回潮）
        assert not re.search(r'"success"\s*:\s*"成功"', text), f"{name} 回潮手写 status 字典"
