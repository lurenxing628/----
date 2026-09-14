---
doc_type: issue-analysis
issue: 2026-09-14-wbui-double-scroll-1366
status: decided
decided: 2026-09-14
decision: B
root_cause_type: layout
related: [wbui-double-scroll-1366-report.md, wbui-double-scroll-1366-fix-note.md]
tags: [workbench, ui, layout, scrolling]
---

# 根因与方案

## 根因

不是某个数值写错，而是滚动模型本身：页面按“文档流 + 每张表自带有界滚动容器”设计，表格容器限高是为了让 sticky 表头 / 首列 / 操作列有包含块。屏幕越矮，限高留给表格的空间越少，而页头、指标卡、筛选行又不会随之收缩，于是两层滚动同时存在且都很短。它在 1080 高的屏上不明显，在 768 高的屏上被放大。

## 候选方案

### A. 矮屏改成“窗口单层滚动”

- 做法：`@media (max-height: 820px)` 下把 `--wb-table-max-height` 设为不限（如 `9999px`），表格随文档流展开，只剩窗口滚动；表头 sticky 改为相对窗口（`top` 取页头高度令牌）。
- 优点：一层滚动，鼠标在哪都一样；改动集中在 `21-table-frame.css` 与页头高度令牌。
- 风险：首列 / 操作列的横向 sticky 依赖容器横向滚动，展开后宽表的横向滚动变成整页横滚，体验更差；38 个表格都受影响，几何合同 G1–G4（`tests/workbench/test_ui_refinement_geometry.py`）需要重新校准。

### B. 矮屏改成“应用式布局”，只滚表格

- 做法：矮屏下让主内容区占满视口高度、页面不滚（`.main-content` 高度 100vh、`overflow: hidden`），指标卡与筛选行压缩为可折叠的一行，表格框用 flex 吃掉剩余高度。
- 优点：保留现有 sticky 模型；表格可视高度最大化，接近“Excel 感”。
- 风险：每个工作区的页头 / 指标区都要适配折叠，工作量分散在多个工作区；计划中心四个内嵌滚动区仍需单独收敛。

### C. 只调数值（不推荐）

- 把 `calc(100vh - 280px)` 改成更激进的 `calc(100vh - 200px)`：矮屏多给表格约 80px，两层滚动依旧存在，只是缓解。

## 推荐

优先 B，理由：不动 sticky 包含块这一稍有闪失就波及 38 个表格的基础假设，把改动限定在“矮屏下页头与指标区可折叠 + 表格框弹性填满”；计划中心的四个内嵌滚动区作为 B 的第二步单独收敛（目录与测算表改为可折叠，甘特板与详情面板共享高度）。

## 用户裁决（2026-09-14）

1. 选 B（矮屏应用式布局，只滚表格）。
2. 阈值只看视口高度 `≤ 820px`（令牌 `--wb-short-screen-max`），不看宽度。
3. 指标卡不折叠、不隐藏，压成一行紧凑数字；产能链在进入某个节点后默认收起成一行快捷切换，可手动展开。
4. 分页推进：第一步批次管理与零件工艺（含基础资料产能链），计划中心四个内嵌滚动区作为第二步单独收敛。

实施见 [wbui-double-scroll-1366-fix-note.md](wbui-double-scroll-1366-fix-note.md)。

## 验证计划（不论选哪个）

- Playwright + Chromium 109 以 1366×768、1920×1080 两档分别对「基础资料 → 零件工艺」「批次管理」「计划甘特」「排产记录」截图，断言 `document.scrollingElement.scrollHeight <= innerHeight`（方案 B）或 `.wb-table-frame` 无纵向滚动条（方案 A）。
- 复跑 `tests/workbench/test_ui_refinement_geometry.py` 与受影响工作区探针；不跑全量门禁。
