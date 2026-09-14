---
doc_type: issue-fix
issue: 2026-09-14-wbui-double-scroll-1366
status: fixed
fixed: 2026-09-14
decision: B
scope: 批次管理、基础资料（零件工艺及产能链）；计划中心内嵌滚动区留作第二步
related: [wbui-double-scroll-1366-report.md, wbui-double-scroll-1366-analysis.md]
tags: [workbench, ui, layout, scrolling]
---

# 修复记录：矮屏应用式布局（方案 B，第一步）

## 做了什么

矮屏（视口高 ≤ 820px，令牌 `--wb-short-screen-max`）下，带 `wb-fill-viewport` 类的工作区改成“应用式布局”：主内容区占满视口、页面不再随窗口滚动，只有表格框滚动；表格以外的内容超过视口时，`main.page-content` 自己滚动兜底。高屏（> 820px）布局与之前完全一致。

### 样式

- `frontend/workbench/app/styles/00-tokens.css`：新增 `--wb-short-screen-max: 820px`（JS 端判断矮屏的唯一来源；`@media` 不能引用变量，三处 `@media (max-height: 820px)` 与之同步，注释已写明）。
- `10-shell.css`：`@media (max-height: 820px)` 下 `.main-content:has(.wb-fill-viewport)` 高度锁 100vh、`overflow: hidden`；`.page-content` 变弹性列并 `overflow: auto` 兜底，上下内边距 20px → 12px；`.page-content` 到 `.wb-fill-viewport` 之间的每一层祖先（含 ResourceLive 的未命名包装 div）用 `:has(.wb-fill-viewport)` 统一变成弹性列，链外兄弟（如产能链 `.rail`）`flex: none`。
- `21-table-frame.css`：`.wb-fill-viewport > .wb-table-frame` 在矮屏下 `flex: 0 1 auto; min-height: 180px; max-height: none`，只收缩不撑大，吃掉剩余高度但不超过表格自然高度。
- `20-controls.css`（唯一允许 `!important` 的文件，每条前有 override 注释）：矮屏下 `.wb-fill-viewport .statline .wb-metric` 压成一行（标签左、数字右，`min-height: 0`、`padding: 5px 12px`），数字字号降到 `--font-size-4`。
- `32-process-trial.css`：矮屏下零件工艺的指标条、阶段页签、两条工具条的外边距收紧。
- `31-batches-resources.css`：产能链收起态样式（`.rail-collapsed`、`.rail-compact` 快捷切换条、`.rail-toggle`），矮屏下收起时隐藏面包屑（快捷切换条已标出当前节点）。

### 组件

- `BatchWorkspace.jsx`、`ProcessWorkspace.jsx`：根节点加 `wb-fill-viewport`。
- `main.jsx`：`main.page-content` 加 `data-wb-scroll-key="page-content"`，让它成为兜底滚动容器时也进入 `WorkbenchNavigation` 的滚动记忆。
- `ResourceRail.jsx`：新增 `useShortScreen()`（`matchMedia`，阈值读令牌，令牌缺失直接抛错）与收起态。规则：矮屏且从总览进入某个节点时默认收起成一行快捷切换（七个节点 + 工作日历，保留 `data-rail-node` 与 `aria-pressed`）；节点之间切换尊重用户当前的展开 / 收起；回到总览或跨过阈值时重算。右上「展开产能链 / 收起产能链」按钮用 `btn link` 变体，高屏不显示。

## 为什么这样做

- 不动表格 sticky 表头 / 首列 / 操作列所依赖的“有界滚动容器”这一基础假设，38 个表格的几何合同不受影响。
- 只对显式挂 `wb-fill-viewport` 的工作区生效，其他页面在矮屏下行为不变，可以逐页推进。
- 没有全局 `:has()` 扫描：所有规则都在 `@media (max-height: 820px)` 且以 `.wb-fill-viewport` 为条件。

## 验证（定向，未跑全量门禁）

- 新增真机测试 `tests/workbench/test_short_screen_layout.py` + `short_screen_layout_probe.cjs`（隔离 Flask + Chromium 109）：1366×768、1366×640（1366×768 屏减去标签栏、地址栏、任务栏）、1280×720、1920×1080 × 批次管理 / 零件工艺，共 8 个用例。矮屏断言：`document.scrollingElement.scrollHeight ≤ innerHeight`、表格框 `max-height: none` 且底边在视口内、工作区没有任何直接子元素被推到折叠线以下、`page-content` 带滚动键；零件工艺另断言产能链默认收起、快捷切换条 8 个节点、展开后窗口仍不滚而 `page-content` 接管滚动、再收起恢复。高屏断言：表格框仍受限高、没有产能链开关。8/8 通过。
- 已登记到 `tools/test_registry_workbench_ui.py` 的 `WORKBENCH_UI_SUPPLEMENTAL_TESTS`（显式选择，不进默认必跑）与 `tests/gate_meta/workbench_round1_registry_support.py`。
- `tests/workbench/resource_rail_probe.cjs`：1366×768 与 1280×720 两档改为先断言“已选节点时默认收起、`.hb-cal-block` 不渲染、快捷切换条保留 `aria-pressed`”，再点「展开产能链」跑原有断言。
- 复跑通过：`node tests/workbench-app-styles.cjs` 0 违规；`tools.scan_ui_copy` 0 命中；注册表与样式源合同 952 通过；`test_resource_readiness` + `test_batch_widgets` + `test_process_widgets` 13 通过；其余受影响探针见 remediation-record 追加段。
- 真机截图（`WB_LIVE_ARTIFACTS` 目录 `short-screen-*.png`）目检：1366×640、1280×720 零件工艺一屏放下产能链快捷条、标题、一行指标、阶段页签、搜索与工具条、表格、分页；批次管理表格与分页也在一屏内。

## 边界与后续

- 本次只覆盖批次管理与基础资料下的零件工艺列表（其余基础资料节点列表由 `ResourceWorkspace` 直接渲染，尚未挂 `wb-fill-viewport`，仍是原布局）。
- 计划中心的目录 / 甘特板 / 详情面板 / 测算表四个内嵌滚动区是方案 B 第二步，未动。
- 排产三页、日历、外协等自带 `vh` 限高的表格未接入，等第一步在真机上用过再逐页挂类。
