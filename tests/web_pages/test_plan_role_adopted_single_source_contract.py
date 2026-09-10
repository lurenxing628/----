"""漂移锁契约：ROLE_ADOPTED / 采用方案标签的唯一字源是 core/models/schedule_plan_role.py。

背景（2026-07-19 全库缺陷扫描 D18/D19）：
- D18：`ROLE_ADOPTED = "adopted"` 曾在 4 个 web 模块被字面重抄
  （navigation_context / scheduler_reports_workbench / scheduler_navigation_links /
  reports_plan_template_fields），已全部改为从 canonical import；
  reports_plan_template_fields 的 DEFAULT_PLAN_LABEL 也曾字面抄写
  "正式采用方案"，已改为 plan_role_label(ROLE_ADOPTED) 派生
  （概念卡 .codestable/semantics/concepts/plan-role.md：标签映射唯一来源 plan_role_label()）。
- D19：GRAPH_CONFIG_PENDING_NOTICE / GRAPH_CONFIG_PENDING_ACTIVE_NOTICE 曾在
  core config_constants 留有一份全仓零消费者的孤儿副本，已删除；
  唯一来源是 web/viewmodels/scheduler_config_panel.py。

注意：CPython 会驻留 "adopted" 这类短字面量，别的模块再抄一份字面定义时
`is` 依然为 True，所以本文件同时做 identity 断言（语义合同）和
源码文本断言（真正拦"再抄一份"的漂移锁）。
"""

from __future__ import annotations

import re
from pathlib import Path

from core.models.schedule_plan_role import ROLE_ADOPTED, plan_role_label

REPO_ROOT = Path(__file__).resolve().parents[2]

# 曾经字面重抄 ROLE_ADOPTED 的 4 个 web 模块（D18 修复面）
_ROLE_ADOPTED_CONSUMER_FILES = (
    "web/navigation_context.py",
    "web/viewmodels/scheduler_reports_workbench.py",
    "web/viewmodels/scheduler_navigation_links.py",
    "web/routes/reports_plan_template_fields.py",
)

# 模块级字面重定义形态：行首 ROLE_ADOPTED = ...（import 行不命中）
_LITERAL_REDEFINITION_RE = re.compile(r"^ROLE_ADOPTED\s*=", re.M)


def test_web_modules_share_canonical_role_adopted_object():
    import web.navigation_context as navigation_context
    import web.routes.reports_plan_template_fields as reports_plan_template_fields
    import web.viewmodels.scheduler_navigation_links as scheduler_navigation_links
    import web.viewmodels.scheduler_reports_workbench as scheduler_reports_workbench

    for module in (
        navigation_context,
        scheduler_reports_workbench,
        scheduler_navigation_links,
        reports_plan_template_fields,
    ):
        assert module.ROLE_ADOPTED is ROLE_ADOPTED, (
            f"{module.__name__}.ROLE_ADOPTED 必须是 core.models.schedule_plan_role.ROLE_ADOPTED 同一对象"
        )


def test_no_literal_role_adopted_redefinition_in_web_modules():
    offenders = []
    for rel in _ROLE_ADOPTED_CONSUMER_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if _LITERAL_REDEFINITION_RE.search(text):
            offenders.append(rel)
        if "from core.models.schedule_plan_role import" not in text:
            offenders.append(f"{rel} (缺 canonical import)")
    assert not offenders, (
        f"ROLE_ADOPTED 字面重定义回潮（唯一来源 core/models/schedule_plan_role.py）：{offenders}"
    )


def test_default_plan_label_derives_from_plan_role_label():
    from web.routes.reports_plan_template_fields import DEFAULT_PLAN_LABEL

    assert DEFAULT_PLAN_LABEL == plan_role_label(ROLE_ADOPTED)
    text = (REPO_ROOT / "web/routes/reports_plan_template_fields.py").read_text(encoding="utf-8")
    assert not re.search(r'^DEFAULT_PLAN_LABEL\s*=\s*["\']', text, re.M), (
        "DEFAULT_PLAN_LABEL 不得再字面抄写，必须由 plan_role_label(ROLE_ADOPTED) 派生"
    )
    workbench = (REPO_ROOT / "web/viewmodels/scheduler_reports_workbench.py").read_text(encoding="utf-8")
    assert "正式采用方案" not in workbench, (
        "scheduler_reports_workbench 不得字面抄写采用方案标签，必须由 plan_role_label(ROLE_ADOPTED) 派生"
    )


def test_graph_config_notice_orphan_copy_stays_deleted():
    # D19：core 侧副本全仓零消费者已删；唯一来源是 viewmodel（viewmodel 层禁 import
    # core.services，若未来要以 core 为源须走 route 注入 + parity 测试，而不是再抄一份）。
    from core.services.scheduler.config import config_constants
    from web.viewmodels.scheduler_config_panel import (
        GRAPH_CONFIG_PENDING_ACTIVE_NOTICE,
        GRAPH_CONFIG_PENDING_NOTICE,
    )

    assert GRAPH_CONFIG_PENDING_NOTICE
    assert GRAPH_CONFIG_PENDING_ACTIVE_NOTICE
    for orphan_name in ("GRAPH_CONFIG_PENDING_NOTICE", "GRAPH_CONFIG_PENDING_ACTIVE_NOTICE"):
        assert not hasattr(config_constants, orphan_name), (
            f"config_constants.{orphan_name} 孤儿副本回潮（D19 已删，唯一来源在 scheduler_config_panel）"
        )
