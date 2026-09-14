---
doc_type: issue-report
issue: 2026-09-14-wbui-double-scroll-1366
status: fixed
fixed: 2026-09-14
severity: P2
created: 2026-09-14
source: .codestable/audits/2026-09-13-frontend-ui-ux-review/finding-07.md
tags: [workbench, ui, layout, scrolling]
---

# 1366×768 上表格内滚与窗口滚动并存

## 现象

在 1366×768 这类矮屏上，工作台主表格自己有一层滚动条，页面也有一层窗口滚动条。鼠标落在表格上滚的是表格，落在表格外滚的是页面；非技术用户经常“想滚页面却滚了表格”，找行、看详情、回表格要来回切换滚动层。计划中心一屏内还叠着目录、甘特板、详情面板、测算表四个内嵌滚动区。

## 复现

1. 浏览器窗口设为 1366×768，打开「基础资料 → 零件工艺」或「批次管理」。
2. 表格框高度被限制在约 488px（`calc(100vh - 280px)`），表格内出现滚动条。
3. 页面本身仍高于视口（页头、指标卡、筛选行、页脚），窗口也可滚动。
4. 鼠标在表格内外滚轮，观察滚动层切换。

## 事实与证据

- 限高令牌：`frontend/workbench/app/styles/00-tokens.css:15` `--wb-table-max-height: calc(100vh - 280px)`；消费处 `21-table-frame.css:4` `max-height: max(180px, var(--wb-table-max-height)); overflow: auto`。
- 各页另有自己的档位：`34-run.css:177` 排产三页 45vh；`34-run.css:185` 排产记录 `calc(100vh - 450px)`；`32-calendar-outsourcing.css:47-94` 日历 / 外协 / 目录 38vh–56vh。
- 计划中心内嵌滚动区：`33-gantt-foundation.css:48`（目录 180px）、`:67`（甘特板 440px）、`:106`（详情面板 `calc(100vh - 96px)` 且 sticky）、`:110`（测算表 270px）；现场实际甘特 `:148`、`:173` 同样两层。
- 详情面板断点 `22-shared-controls.css:32` 是 `@media (max-width: 1279px)`，按视口算；1366 不触发，面板与表格并排，不构成额外负担（审计复核已把“断点错”这条推翻）。
- 内滚的存在理由：`21-table-frame.css:1` 注释写明“内部滚动给每个 sticky 单元格一个有界的包含块”——表头、首列、操作列的 sticky 都依赖这个滚动容器。

## 影响范围

所有使用 `.wb-table-frame` 的表格（38 个 JSX 文件共用 `table.wb-table`），以及计划中心、现场实际甘特的自绘滚动区。

## 关联

- 审计 finding-07（P2，open）；P2-L1「内嵌滚动位置不保留」已在 2026-09-13 修复（`WorkbenchNavigation.js` 按 `data-wb-scroll-key` 记忆与恢复），本问题不再与它叠加。
