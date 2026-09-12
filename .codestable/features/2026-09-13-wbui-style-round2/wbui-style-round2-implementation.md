---
doc_type: feature-implementation
feature: 2026-09-13-wbui-style-round2
status: implemented
summary: 按 2026-09-13 整体样式复审意见实施第二轮整改：固定列滚动阴影、表头不折行、单一页面标题、统一容器与 KPI 条、甘特自适应高度、原因文字收口、重复文案合并、链接蓝收敛、间距/行高/圆角令牌接线
tags: [workbench, ui, css, tokens, tables, regression]
---

# 背景

- 来源：2026-09-13 对 15 个视图在 1280 / 1920、明暗两套主题的真机截图复审，加一轮样式层逐文件统计（颜色零硬编码、间距无栅格、行高无令牌、断点 18 个、`20-controls.css` 混入 30 个业务类名）。用户决定"按照意见改"。
- 边界：只改 `frontend/workbench/app/` 消费层、共享模块与 `styles/` 应用样式层，对应测试和 CodeStable 文档；不改原型层快照、领域 API、DTO；不触碰他人未提交的排产优化器改动。工作区仍含他人未提交内容，本记录不是 clean-worktree proof。

# 改动

## 1. 表格

- 新增 `WorkbenchScrollShadows.js`（登记进 `build-order.json` live 列表，`main.jsx` 在 `.main-content` 挂载一次）：对每个 `.wb-table-frame` 监听 scroll 与 ResizeObserver，按实际是否有列被固定列遮住打 `data-overflow-left/right` 标记。CSS 只在有标记时给 `.wb-col-actions` / `.wb-col-key`、报表 `.rw-fixed-action/.rw-fixed-key`、校准明细固定列叠加柔和阴影；表格放得下时没有任何阴影。阴影色走新令牌 `--wb-scroll-shadow`（浅色 `--ui-info-muted`，深色 `--ui-bg`）。
- 表头 `word-break: keep-all`：中文列名只在空格或斜线处换行，不再出现"数据 / 域"、"本次数 / 量"。主数据总览 `数据域` 列 84→96、逐次报工表 `本次数量` 7%→9% 让列名放得下；`.mo-column span` 的 `overflow-wrap` 改回 normal。
- 批次表列宽未压缩：几何门禁 G1 要求批次表在 1280 下横向溢出以验证固定列，这是被测试固化的既有行为；阴影与原生滚动条共同承担"下面还有列"的提示。
- 可排序表头按钮继承表头颜色，不再是链接蓝；批次表按 `aria-sort` 显示 ▲/▼。折叠开关（`summary`）改为正文色、悬停变蓝。编号链接保留蓝色，作为表格里唯一的链接色。

## 2. 壳层

- 页面标题只保留顶栏一份：11 个工作区的页内 `h2` 加 `wb-page-title`（视觉隐藏、仍在 DOM 供结构与辅助技术使用），副标题加 `wb-page-context`（13px 次级色）成为可见的上下文行。涉及值班台、主数据总览、批次列表、执行排产、方案试调、现场记录、现场实际甘特、报表中心 / 执行复盘、工时定额校准、系统管理、排产历史（含各错误态）。工艺节点标题、候选子态标题不属于重复，保持可见。
- 值班台与基础资料的 `.plana` 根补 `padding: 0`，全部页面内容左边缘统一在 264px。主数据总览与现场记录的整页白卡改为透明，页面统一为"灰底 + 白卡（表格、KPI、详情）"。
- KPI：值班台 7 张卡改 flex 换行并伸展，1280 下 4+3 不再留空洞；主数据总览 1280 下总览四格保持一行；现场实际甘特的行内 KPI 改为与其他页一致的四格条（label 上、数值下，`aria-label="当前范围概况"`）。
- 执行排产页的单按钮灰带取消，"排产记录"作为 `PreflightWorkspace` 的 `actions` 放进标题行；指定运行子态仍保留导航条。选择排产方案页的 `.scheduling-navigation` 去掉灰底与下边线，只保留按钮行。

## 3. 空态、原因文字、重复文案

- 计划甘特 `.plan-board` 与实际甘特 `.fg-board` 改为 `height:auto` + `max-height`（原定高 410/480），只有一行时不再留 300px 空白；`min-height:160px` 保证空态可见。值班台 `.dy-work` 去掉 590px 最小高度。
- `ResourceControls.Button` 的 `reasonDisplay` 明确为 `'inline' | 'tooltip'`（其他值抛错）。tooltip 模式把原因放进 title 与视觉隐藏的 `aria-describedby` 说明节点；表格操作列与工具栏的 12 处禁用按钮改用 tooltip（批次删除、校准预览采用 / 导出全部筛选 / 打开建议、基础资料与工艺批量删除、报工补齐 / 更正、资源目录编辑 / 删除、候选详情）。表单底部与页面级主动作保持 inline。
- `ResourceControls.Issues` 按 message 合并重复条目并显示"（N 条）"，现场记录黄框不再连打三遍同一句。
- 任务详情面板未选中任务时只渲染一段说明，不再五个小节各写"尚未选中任务"。

## 4. 令牌接线

- 间距：`padding/margin/gap` 里精确等于 4/8/12/16/24/32 的字面量全部改为 `var(--space-1..6)`（600 处）；`gap` 与 `margin` 的 5/6/10/14 收敛到相邻阶梯（125 处）。`padding` 里的 6/10/14 仍保留字面量，避免改动元素盒尺寸触发几何断言，属遗留。
- 行高：新增 `--wb-line-tight/body/relaxed`（1.3/1.5/1.7）并接线 30 处精确匹配；其余 15 种取值未收敛。
- 圆角：字面量 `4px` 与别名 `--wb-control-radius` 统一为 `--wb-radius-control`。
- 断点：`1350px` 归到 `1366px`；删除无引用的 `--wb-content-min`。`1279/1280` 语义不同（"小于 1280" 与"含 1280"），保留。

## 5. 未做与理由

- `20-controls.css` 里 30 个业务类名的迁出：`workbench-app-styles.cjs` 只允许 `!important` 出现在该文件，迁出等于放弃这层护甲并逐条重验原型层级联，属独立重构，未做。
- 主按钮背景令牌未改：深色下 `--ui-primary`（#3b82f6）配当前文字色对比度约 3.9:1，低于 AA；现有 `--ui-info-text` 映射语义反直觉但可访问，保留。
- 深色次级文案维持 `--ui-muted`：`test_secondary_copy_contrast.py` 与 `secondary_copy_metrics.cjs` 锁定深色不变，且 #94a3b8 在深色卡片上对比度已达 6.3:1；曾改为 `--ui-info-muted` 后据测试还原。

# 文件

- 新增：`frontend/workbench/app/WorkbenchScrollShadows.js`。
- 修改：`main.jsx`、`ResourceControls.jsx`、`PlanDetailsUI.jsx`、`SchedulingWorkspace.jsx`、`PreflightWorkspace.jsx`、`DashboardWorkspace.jsx`、`MasterOverviewWorkspace.jsx`、`MasterOverviewContract.js`、`BatchWorkspace.jsx`、`BatchTable.jsx`、`TrialWorkspace.jsx`、`FieldWorkspace.jsx`、`FieldDetail.jsx`、`ActualGanttWorkspace.jsx`、`ReportWorkspace.jsx`、`CalibrationWorkspace.jsx`、`CalibrationAdoptionAction.jsx`、`CalibrationControls.jsx`、`CalibrationWorkspace.jsx`、`SystemLive.jsx`、`RunHistoryWorkspace.jsx`、`RunJobControls.jsx`、`ResourceWorkspace.jsx`、`ResourceCatalog.jsx`、`ProcessWorkspace.jsx`；`styles/` 全部 17 个文件；`scripts/workbench/build-order.json`；`static/workbench/` 重建。
- 测试：`tests/workbench/app_styles_geometry_probe.cjs` 新增滚动阴影三段式与表头 keep-all 断言。全目录长跑归因后再改（见补记）：`final_execution_field.cjs`、`final_execution_controls.cjs`、`point_downstream_browser.cjs` 期望改回 HEAD 语义；`final_foundation_live_actions.cjs` / `final_foundation_live.cjs` 滚动守卫与"至少一个视口真实滚动"检查；`final_operations_edges.cjs` 改断言维护屏稳定态；`shared_controls_probe.cjs` 旧 `title` 模式改 `tooltip`；`test_ui_navigation_guard.py` 页签合同改回整体恢复。

# 验证

| 范围 | 结果 |
| --- | --- |
| `node tests/workbench-app-styles.cjs` 样式层静态合同 | violations 为空 |
| `tests/workbench/app_styles_geometry_probe.cjs`（1280/1366/1920 × 明暗） | 6 例通过：放得下时无阴影，溢出时遮住列的一侧有阴影，滚到底阴影消失 |
| 表格相关 8 个 pytest 模块（批次、排产历史、工时定额、值班台、值班台细化、校准谱系、报表、主数据总览） | 23 passed |
| 节点合同 + 上述模块 + 导航守卫 + 次级文案对比 + 登记合同（令牌接线后） | 927 passed / 2 skipped / 1 failed → 失败为深色次级文案合同，已按合同还原后 4 passed |
| `tests/gantt`、`tests/web_pages`、`tests/gate_meta`、`tests/app_runtime` 相关 8 个模块 | 1262 passed |
| 15 视图真机截图（1280 明暗、1920 浅色，Chromium 109） | 全部无 pageerror；逐张目检见本记录第 2、3 节 |
| `tests/workbench` 全目录（8398 例，1 小时 22 分） | 9 failed / 8376 passed / 13 skipped；9 例归因与处理见补记，处理后定向复跑 8 例 + 共享控件探针全部通过 |
| 干净 HEAD worktree 上复跑同 8 例（基线归因） | 8 passed，证明失败全部来自工作区未提交改动 |
| 处理后复跑：8 例真机用例 | 8 passed（6 分 47 秒） |
| 处理后复跑：`test_shared_controls_widgets.py`、`test_ui_navigation_guard.py`、`test_reports_workbench_navigation_contract.py` | 1 + 23 passed |

未跑：完整门禁与 daily gate（工作区含他人未提交改动）；e696 浏览器矩阵与 `ui_refinement_gate.py` 基线未重采，第二轮改动后的几何基线需要重新采集。按用户要求，处理 9 例后不再重跑全目录。

# 补记：全目录长跑归因（2026-09-13）

全目录 9 个失败在干净 HEAD worktree 上全部通过，因此都来自工作区未提交的改动（他人的界面整改、复审修复、本轮样式整改）。逐条归因：

| 用例 | 根因 | 处理 |
| --- | --- | --- |
| `final_execution_browser[execution-field]`、`final_execution_controls` | 他人未提交的测试改动把工时期望改成固定 1 位小数（`3.0 h`、`2.0 h`），锁的是回归后的格式；复审修复第 1 项已把显示恢复为 HEAD 的最多 3 位去尾零（`3 h`、`2 h`） | 期望改回 HEAD 语义 |
| `point_downstream_browser[with-real-reports]` | 同上：作业时间线坐标轴期望被改成不带秒（`09:50`），HEAD 与当前都带秒 | 期望改回 `09:50:00` |
| `final_execution_analytics`、`final_execution_report_reentry[review]`、`final_execution_reports` | 复审修复第 3 项把页签切换改成"目标旧上下文叠加当前 scope/topic"，复盘 topic 压到报表保存的 table 上触发"报表专题、排序或分页无效"且不发请求，重进复盘时保存的 `query` 被空值覆盖；HEAD 与整改版都是整体恢复，属验收锁定设计 | 回退 `navigate` 为整体恢复，同步改回 `test_ui_navigation_guard.py` 合同与复审记录 |
| `final_foundation_live` | 甘特板自适应高度后，1920×1080 下只有一行安排的甘特页整页放得下，测试假设主内容区必然可滚动而等待滚轮位移超时（1392×924 同步骤通过） | `userScroll` 先量可滚空间，放得下时记录跳过并沿用当前位置；长跑结束时要求至少一个视口真实滚动过 |
| `final_operations_edges` | 竞态：创建备份存储故障后，页内"维护原请求结果"里的"需人工恢复核查"只在主机状态回查前的几十毫秒存在，随后整页换成维护屏；HEAD 上 2 次也有 1 次失败 | 断言改为维护屏稳定态（"结果未知，需人工核查"标题、故障消息、无"确认结果"按钮、有"核实原请求"） |
| `test_shared_controls_widgets` | 探针夹具仍用 `reasonDisplay:'title'` 旧模式，本轮 Button 收紧为 `'inline' \| 'tooltip'` 后抛错，夹具挂载超时 | 夹具改用 `tooltip` 并补隐藏说明、无可见原因的断言 |
