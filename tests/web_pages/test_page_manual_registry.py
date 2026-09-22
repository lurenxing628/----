"""回归测试：页面级“本页说明”注册表与说明书章节的契约——注册表以工作台 15 个视图 id 为键、标题与 VIEW_TITLES 一致、登记的章节标题在说明书里恰好出现一次、相邻视图都已登记、旧端点表为空；说明书正文保留用户校正过的关键说法，并且不再出现已退役页面和旧口径。"""

from __future__ import annotations

import re
from typing import List

import pytest

from tests._support.paths import REPO_ROOT
from web.routes.workbench.navigation_metadata import VIEW_ALIASES, VIEW_TITLES
from web.viewmodels import page_manuals_registry as registry

MANUAL_PATH = REPO_ROOT / "static/docs/scheduler_manual.md"

#: 用户逐条校正过的说法，改说明书时不能把它们改没。
USER_CORRECTED_FULL_MANUAL_PHRASES = (
    "最后更新：2026年9月",
    "值班台怎么看",
    "工时留空不会自动补零",
    "效率按 **百分比** 填：正常效率写 `100`，不是 `1`",
    "`自制工种编号` 一台设备只能绑一个，而且必须是自制工种",
    "同一个人只能有 1 台主操设备",
    "文件导入只做增量，不会删除任何一天",
    "备份文件名由系统自动按时间和用途生成",
    "只看历次排产的范围、时间、候选数和安排数",
    "这里不能导出，也不能把某次排产恢复成当前数据",
    "部分报表导出可能只是直接下载文件，不一定都有操作记录",
    "不生成版本、不写入业务或审计数据",
    "试调不影响正式计划",
    "采用后这个模板工序的单件工时就锁定了，不能撤销",
    "只要预检里有一行被拒绝，确认按钮就点不下去",
)

#: 已退役页面、旧口径和词表停用的说法；2026-09-21 审计时这些句子还留在说明书里。
RETIRED_OR_FORBIDDEN_PHRASES = (
    "备份与恢复", "系统历史", "OR-Tools", "贪心", "step-by-step", "CV值", "均匀程度 CV", "单件时间",
    "右下角“本页说明”", "改工种名或工种编号前", "版本分析", "证据",
    "导出周计划", "周计划表", "停机计划", "批次物料需求", "班组管理", "基础资料 → 班组", "管理样例",
    "灰色入口", "灰色禁用按钮", "不能点击", "继续生产", "报异常",
    "本次排产会报错并停止", "系统不会自动跳过这些批次", "只打开当前页面的速览卡片",
    "系统管理 → 使用说明", "走打印页", "常用方案", "保存为方案", "恢复默认设置", "执行排产与试调",
    "个人工作日历", "解除锁定", "排产版本", "版本下拉", "计划信息条", "体检表", "临期批次",
)


@pytest.fixture(scope="module")
def manual_text() -> str:
    return MANUAL_PATH.read_text(encoding="utf-8")


def _headings(text: str) -> List[str]:
    """标题清单；围栏代码块里的 # 不算标题，和 legacy_presentation.manual_blocks 同一规则。"""
    headings, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(2))
    return headings


def test_registry_keys_match_workbench_views() -> None:
    assert set(registry.VIEW_MANUALS) == set(VIEW_TITLES)
    assert registry.MANUAL_VIEW_IDS == tuple(registry.VIEW_MANUALS)
    for view, entry in registry.VIEW_MANUALS.items():
        assert entry["title"] == VIEW_TITLES[view], view
    # 页签别名（计划甘特 / 交付风险 / 执行复盘）各有自己的章节，不借用父视图的说明。
    for alias, parent in VIEW_ALIASES.items():
        assert alias in registry.VIEW_MANUALS and parent in registry.VIEW_MANUALS
        assert registry.VIEW_MANUALS[alias]["heading"] != registry.VIEW_MANUALS[parent]["heading"]


def test_registry_entries_are_well_formed() -> None:
    for view, entry in registry.VIEW_MANUALS.items():
        assert set(entry) == {"title", "heading", "summary", "related"}, view
        assert isinstance(entry["heading"], str) and entry["heading"].strip() == entry["heading"] and entry["heading"], view
        assert isinstance(entry["summary"], str) and entry["summary"].strip(), view
        related = entry["related"]
        assert isinstance(related, tuple) and 1 <= len(related) <= 4, view
        assert len(set(related)) == len(related) and view not in related, view
        assert set(related) <= set(registry.VIEW_MANUALS), (view, related)


def test_registry_headings_exist_exactly_once_in_manual(manual_text: str) -> None:
    headings = _headings(manual_text)
    for view, entry in registry.VIEW_MANUALS.items():
        assert headings.count(entry["heading"]) == 1, (view, entry["heading"])
    assert registry.VIEW_MANUALS["dashboard"]["heading"] == "值班台怎么看"
    assert registry.VIEW_MANUALS["process"]["heading"].startswith("5. ")
    assert registry.VIEW_MANUALS["system"]["heading"].startswith("11. ")


def test_manual_entry_lookup_is_exact_and_returns_a_copy() -> None:
    for missing in (None, "", "   ", "nope", "scheduler.gantt_page", "dashboard_first_run"):
        assert registry.manual_entry(missing) is None, missing
    entry = registry.manual_entry("dashboard")
    assert entry is not None and entry["view"] == "dashboard" and entry["title"] == "值班台"
    gantt = registry.manual_entry(" gantt ")
    assert gantt is not None and gantt["view"] == "gantt"
    entry["title"] = "改掉"
    assert registry.VIEW_MANUALS["dashboard"]["title"] == "值班台"


def test_legacy_endpoint_tables_are_empty() -> None:
    # 旧路由层的端点键已随旧页面退役；三个名字只为既有导入不断，不能再往里加条目。
    assert registry.ENDPOINT_TO_MANUAL_ID == {}
    assert registry.MANUAL_ENTRY_ENDPOINTS == {}
    assert registry.ENDPOINT_OVERRIDES == {}


def test_manual_keeps_user_corrected_phrases(manual_text: str) -> None:
    missing = [phrase for phrase in USER_CORRECTED_FULL_MANUAL_PHRASES if phrase not in manual_text]
    assert not missing, missing


def test_manual_drops_retired_pages_and_wording(manual_text: str) -> None:
    present = [phrase for phrase in RETIRED_OR_FORBIDDEN_PHRASES if phrase in manual_text]
    assert not present, present


def test_manual_old_name_table_points_to_current_views(manual_text: str) -> None:
    table = manual_text.split("### 旧名称 → 现在叫什么", 1)[1].split("\n\n这份说明书", 1)[0]
    for needle in (
        "| 试调排产方案 | 排产 → 试调排产方案 |",
        "| 导出计划 | 选择排产方案 → 导出",
        "“概况、备份恢复、运行日志、配置”四个页签",
        "| 本页说明 | 顶栏“帮助”打开",
    ):
        assert needle in table, needle
    assert "本页说明" in manual_text and "阅读整本说明书" in manual_text and "下载整本说明书" in manual_text
    for view, entry in registry.VIEW_MANUALS.items():
        assert entry["title"] in manual_text, (view, entry["title"])
