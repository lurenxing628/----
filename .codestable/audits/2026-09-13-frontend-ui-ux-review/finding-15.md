---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-15"
nature: usability
severity: P2
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 15：候选工作区行动区导航类与动作类按钮无分组并列

## 速答

候选排产结果工作区工具栏把「返回排产记录」「返回正式计划」「采用方案」（主按钮，写正式计划）「试调」「刷新」一字排开，无分组无说明。路线图 `wbui-run-stepper` 已让只有「采用方案」是实心主按钮，视觉层级有了；剩下的问题是承诺级别最高的「采用」与最随意的「试调」紧挨着，导航类按钮又与动作类混排。

## 关键证据

- `frontend/workbench/app/RunCandidateWorkspace.jsx:109-114` — 五个控件并列渲染：两个「返回…」、`renderAdoption` 产出的「采用方案」、「试调」、图标式「刷新候选方案」。
- `frontend/workbench/app/DashboardWorkspace.jsx:85` — 方案对比页头部 caption「尚未确认所选候选方案」，第一眼是未确认警告。

## 影响

新用户面对 5 个去向概念停滞；采用与试调误触路径短。

## 修复方向

行动区分组：导航类（返回…）降为链接样式并靠左，动作类（采用 / 试调）靠右并加分隔，试调处标注「不影响正式计划」。

## 建议动作

`cs-issue`，工具栏布局调整，配合截图走查。

## 复核记录（2026-09-13）

- 由 P1 降为 P2：`wbui-run-stepper`（done）已处理主按钮层级，剩余是分组问题。
- 坐标由构建产物 `:293-316`、`DashboardWorkspace.js:233` 改为源码。

## 实施记录（2026-09-13）

- 状态：partially-resolved。`RunCandidateWorkspace.jsx` 分 `rc-nav` / `rc-actions` 并加分隔与下划线弱化；真正的链接样式按钮需在 `20-controls.css` 增加受控变体，未在本轮引入。
- 详见 [remediation-record.md](remediation-record.md)。

## 补充（2026-09-14）

- 状态：resolved。链接样式按钮变体已作为专项 `.codestable/features/2026-09-14-wbui-link-button-variant/` 落地：`20-controls.css` 新增 `button.btn.link`，候选页两个返回按钮改用该变体。
