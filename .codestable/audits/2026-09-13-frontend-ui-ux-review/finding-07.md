---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-07"
nature: usability
severity: P2
confidence: high
suggested_action: cs-refactor
status: resolved
reviewed: 2026-09-13
resolved: 2026-09-14
---

# Finding 07：1366×768 上表格内滚与窗口滚动并存的双层滚动

## 速答

表格框限高公式在 768px 高的屏上只给表格 488px，内部滚动；页面本身又有窗口滚动，鼠标落点决定滚哪一层，非技术用户常出现「想滚页面却滚了表格」。详情面板在 1366 宽的窗口里仍与表格左右并排，不构成额外负担。

## 关键证据

- `frontend/workbench/app/styles/00-tokens.css:15` — `--wb-table-max-height: calc(100vh - 280px)`，768px 屏为 488px；`21-table-frame.css:4` — `max-height: max(180px, var(--wb-table-max-height)); overflow: auto`；执行排产三页 `34-run.css:170` 另用 45vh。
- 详情面板断点 `22-shared-controls.css:32-35` 是 `@media (max-width: 1279px)`，按视口宽度计算，1366 宽窗口不触发。整改前后两套 1366 截图（`evidence/workbench-ui/2026-09-12-final/baseline-current/` 与 `browser-e696/` 的 `analysis-1366-768-light-selected.png`）里「任务详情」都在右侧并排。
- 计划中心同屏 4 个内嵌滚动区：`33-gantt-foundation.css:48,67,106,110`（目录、甘特板、详情面板、测算表）。
- 侧栏宽度 240px（`prototype/tokens/colors.css:85`），1366 窗口主区约 1126px，可容纳 320px 详情面板（`00-tokens.css:11`）并排。

## 影响

滚轮行为随鼠标位置变化，找行、看详情、回表格要来回切换滚动层。与 P2-L1「内嵌滚动位置不保留」叠加后，切走再切回还要重新定位。

## 修复方向

评估限高公式在 768 高屏上给主表更多可视高度，或在窄高屏减少同屏嵌套滚动区数量；与 P2-L1 的滚动位置恢复合并处理。不需要动详情面板断点。

## 建议动作

`cs-refactor`，布局与滚动模型调整，需 1366×768 实机验证。

## 复核记录（2026-09-13）

- 原「详情面板断点 1279px 是主区宽度，1366 减 240 侧栏后恒处详情下排」不成立：断点是视口媒体查询，1366 不触发，截图亦证明并排。原标题与核心论断改写。
- 原侧栏 240px 事实正确，推论错误。
- 由 P1 降为 P2。

## 实施记录（2026-09-13）

- 状态：open。未动：布局与滚动模型调整立为专项 `.codestable/issues/2026-09-14-wbui-double-scroll-1366/`。
- 详见 [remediation-record.md](remediation-record.md)。

## 实施记录（2026-09-14）

- 状态：resolved（表格页第一步）。用户拍板方案 B：矮屏（视口高 ≤ 820px）下批次管理与零件工艺改成应用式布局，页面不滚只滚表格，指标条压成一行，产能链默认收起成一行快捷切换，超出时 `page-content` 兜底滚动；高屏不变。
- 真机验证：新增 `tests/workbench/test_short_screen_layout.py`，1366×768 / 1366×640 / 1280×720 / 1920×1080 共 8 用例通过。
- 未动：计划中心四个内嵌滚动区（方案 B 第二步）、其他基础资料节点列表与排产 / 日历 / 外协自带 `vh` 限高的表格。详见 `.codestable/issues/2026-09-14-wbui-double-scroll-1366/wbui-double-scroll-1366-fix-note.md`。
