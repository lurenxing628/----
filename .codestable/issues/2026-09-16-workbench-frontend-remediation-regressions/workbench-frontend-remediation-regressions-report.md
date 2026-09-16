---
doc_type: issue-report
issue: 2026-09-16-workbench-frontend-remediation-regressions
status: resolved
resolved: 2026-09-16
severity: P1
created: 2026-09-16
source: 2026-09-16 补集通道实跑日常门禁之外的浏览器探针，三位复审代理各自定向复现并归因
tags: [workbench, frontend, gantt, theme, short-screen, regression]
---

# 手册整改前端（4edd95d3 / a06de630）带入的三处真实回归

补集通道（必跑组 target_paths 之外的 603 个测试文件）实跑后，55 个浏览器探针失败里绝大多数是探针文案过期，
但有三处核对为产品侧行为回归。三处都已按根因修复并重建静态资产。

## 1. 现场实际甘特：开关键链后悬停资源分组，条带与行无限抖动

- 现象：勾选“关键链”后把鼠标停在资源分组标签上，条带在“正在读取所选工序的关联链…”与“计划关键链（近似）”之间
  反复闪烁，行上下跳动，`/actual-gantt/chain` 请求数为 0。
- 机制：悬停 → `onChainTarget(members)` → `relatedChain` 置 busy、`chain` 为空 → `<Chain>` 卸载，槽里只剩提示条；
  基线 `.fg-chain-slot { height:160px; overflow:auto }` 保证槽高不变，4edd95d3 改成 `min-width:0` 后槽高随内容塌缩
  约 96px，分组行上移到指针之外触发 mouseleave → 条带挂回 → 行回落 → 再次 mouseenter……120ms 防抖被每次翻转取消。
- 修复：`ActualGanttWorkspace.jsx` 记住最近展示的链，读取期间继续渲染上一条带；`33-gantt-foundation.css` 让
  `.fg-chain-strip + .fg-note` 以覆盖层叠在条带右上角（z 层级用 `--wb-z-sticky` 令牌），槽高不再随状态变化。
- 验证：`tests/workbench/test_final_execution_chain.py` 14 passed（修前三次单跑均卡 final_execution_chain.cjs:70）。

## 2. 深色主题下计划中心视图选中页签对比度 3.98:1

- 现象：`tests/workbench/test_run_presentation.py` 深色变体在 candidate-first-screen 报 `ratio 3.977 < 4.5`。
- 机制：main.jsx:79 给 `.wb-view-tabs` 加了 `wb-surface plan-view-tabs`，页签底色从透明（落在 --ui-bg #0f172a 上，4.85:1）
  变成 --ui-card-bg #1e293b；选中色仍是 --ui-primary #3b82f6，只剩 3.98:1。浅色 #2563eb 对白 5.17:1 不受影响。
- 修复：`00-tokens.css` 新增应用层令牌 `--wb-tab-selected`（根：--ui-primary；`html[data-theme="dark"]`：
  --ui-primary-hover #60a5fa，对卡底 5.75:1），`11-navigation.css` 选中页签改用该令牌。原型令牌快照未动。

## 3. 1366×640 矮屏下零件工艺分页器被推到折叠线以下

- 现象：`tests/workbench/test_short_screen_layout.py` 报 `process@1366x640: nothing in the workspace is pushed below the fold + ['wb-pager']`，
  违反 2026-09-14 矮屏方案 B 合同（issue 2026-09-14-wbui-double-scroll-1366）。
- 机制：ProcessWorkspace.jsx:145 把阶段页签与两条工具条包进新增 `.process-list-controls` 卡片，
  `32-process-trial.css` 给它的内外距/分隔线规则特异性 0,3,0，压过矮屏媒体查询里 `.wb-fill-viewport .subtabs/.toolbar`
  的 0,2,0 压缩规则，比基线多占约 19px，表格框已缩到 180px 下限后分页器出界。
- 修复：在卡片规则之后补一段 `@media (max-height: 820px)`，用 `.process-workspace.wb-fill-viewport .process-list-controls`
  把外距、底距、页签下距与两条工具条之间的分隔收紧到与基线等量。

## 为什么门禁没拦住

三个探针都不在日常门禁必跑组里，只在 CI 全量门禁执行，而 CI 全量门禁自 6 月起就因 45 分钟超时从未跑到测试阶段
（见 issue 2026-09-16-ci-quality-gate-45min-timeout）。建议把 `test_final_execution_chain.py`、`test_run_presentation.py`、
`test_short_screen_layout.py` 登进 workbench 相关必跑组。
