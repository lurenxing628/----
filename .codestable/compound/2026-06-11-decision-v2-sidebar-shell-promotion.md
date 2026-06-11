---
doc_type: decision
date: 2026-06-11
slug: v2-sidebar-shell-promotion
title: V2 侧栏壳转正为唯一 UI，删除 V1/V2 双轨机器（render_bridge/ui_mode 五件套）
status: decided
owner: lurenxing
source: 2026-06-10 前端全面设计评审（23 agent workflow 三评委裁定）+ 2026-06-11 用户拍板（fusion roadmap 六项拍板第①项）；证据档案 .codestable/roadmap/aps-frontend-fusion/drafts/capability-mining.md（v2-shell-inventory 域）
---

# 决策：V2 侧栏壳转正，双轨 UI 机器退役

## 一句话结论

`web_new_test/` 的 V2 侧栏壳**转正为唯一壳**（搬进 `templates/`），V1 顶栏壳与整套双轨切换机器（render_bridge.py、ui_mode.py、ui_mode_request.py、ui_mode_store.py、routes/system_ui_mode.py 共 5 文件）**删除不留兼容垫片**。

## 为什么是侧栏壳（而不是 V1 顶栏壳）

- DEFAULT_UI_MODE="v2" 自 2026 年初起就是生产默认，用户在侧栏壳里实际生活了约 4.5 个月——切回 V1 是用户可感知的倒退，转正 V2 用户零感知。
- 设计评审三评委一致选「方向 B：设计系统中改」，其顶栏方案是按 V1 壳设计的；合成裁决修正为「V2 侧栏转正承载 B 的设计系统」——工程账是纯减法（删 548 行双轨机器 + 34 处 import 改一行），且侧栏天然承载 roadmap 4.3 的「做事路线」分组导航。
- 2026-06-11 用户明确拍板："留左侧菜单栏那个"。

## 决策内容（六工作包，fusion-dual-track-retirement 实施）

1. V2 base.html 改造后搬进 templates/（静态链 url_for('static')、title 块修常量化回归、删双轨探针 meta）；style.css 搬 static/css/。
2. 删 5 文件：web/render_bridge.py(244)、ui_mode.py(80)、ui_mode_request.py(59)、ui_mode_store.py(71)、web/routes/system_ui_mode.py(94)。
3. 34 个路由文件 `from web.ui_mode import render_ui_template as render_template` 一次性切回 `from flask import render_template`，不留垫片。
4. init_ui_mode 的模板全局注入（get_help_card/build_workbench_navigation_links 等）搬进 factory，否则宏断供。
5. 打包 bat 与 tools 门禁源同步（LIVE 源 6 处硬编码 web_new_test/ui_mode 路径）；quality_gate_ledger 台账同步。
6. 测试面：整删 test_ui_mode.py(511)、test_ui_mode_startup_guard_observability.py(85)，改约 16 文件；web_new_test/ 整树删除（6 镜像模板已由 mirror-sync-guard 钉死一致，转正即继承）。

## 被拒方案

- **保留双轨长期并行**：每个模板改动付双写税（镜像守卫只是临时止血），词表/样式收编工作量×2，已实际造成「入口只挂 V1、默认界面不可见」级别的旗舰缺陷。
- **转回 V1 顶栏壳**：用户已习惯侧栏 4.5 个月；V1 壳还要再造侧栏分组导航的家。
- **保留 ui_mode 机器仅锁死 v2**：548 行死机器养着、新人持续误解为可切换，违背"删干净不留垫片"的项目纪律。

## 约束与后续

- 实施排在 fusion-mirror-sync-guard（已 done）之后：守卫保证转正搬家瞬间双树一致。
- versioned url_for 由 static_versioning.py 的 context_processor 兜底，不依赖 render_bridge 每请求注入（已核证）。
- 退役后 mirror-sync-guard 测试随 web_new_test/ 一并删除。
