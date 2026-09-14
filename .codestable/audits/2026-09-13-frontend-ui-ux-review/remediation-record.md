---
doc_type: audit-remediation-record
audit: 2026-09-13-frontend-ui-ux-review
created: 2026-09-13
reviewed: 2026-09-13
status: implemented
scope: 本审计 P1 12 条 + P2 38 条的实施记录；观察项 O1–O4 未动
verification: 定向验证（样式门禁 / 文案扫描 / UI 必需组 / 注册表合同 / 受影响浏览器探针），未跑全量门禁
---

# 前端 UI/UX 审计整改实施记录（2026-09-13）

## 约束与口径

- 用户要求：P1、P2 全部实施；**不跑全量质量门禁**（耗时数小时），只跑触及组件的定向测试与探针。
- 工作区里另有一批与本轮无关的遗留未提交改动（前端文案清扫等），本记录只列本轮触碰的文件。
- 所有用户可见文案通过 `tools.scan_ui_copy`（0 命中），遵守 `.codestable/compound/2026-09-13-decision-ui-copy-glossary.md`。
- 样式改动全部走令牌，`node tests/workbench-app-styles.cjs` 0 违规；本轮新增门禁规则 `undefined-variable`（见 finding-03）。

## P1 处理结果

| # | 结果 | 落点 |
|---|---|---|
| 01 甘特红绿仅靠色相 | 已修 | `00-tokens.css` 新增 `--wb-gantt-critical-stripe` / `--wb-gantt-overlap-stripe`（斜纹）与 `--wb-gantt-success-ring`（2px 内环）；`33-gantt-foundation.css`、`33-plan-gantt.css`、`32-process-trial.css` 的条与图例同时消费；`RunCandidateGantt.jsx` 重叠条改用 overlap 色系并画斜纹 |
| 02 暗色 hover 无反馈 | 已修 | `前端设计/tokens/dark.css` `--ui-table-row-hover-bg: #334155`，经 `import_prototype.py --update` 进快照 |
| 03 来源切换选中态引用不存在令牌 | 已修 | `34-run.css:158` 改用 `--ui-info-text` / `--ui-info-bg` / `--ui-primary`；`tests/workbench-app-styles.cjs` 新增 `undefined-variable` 规则（收集 styles / prototype 声明与 app JS 里带引号的变量名），`WorkbenchControlStyles.jsx` 把 4 个 `--wb-control-*-icon` 写成显式常量表 |
| 04 现场「计划」条 1.36:1 | 已修 | `35-field.css:15` `.planned` 填充 + `inset 0 0 0 1px var(--ui-info-text)` |
| 05 数字未等宽 | 已修 | `20-controls.css` `table.wb-table tbody td { font-variant-numeric: var(--num-variant) }`；`--num-variant` 从零消费变为全表消费 |
| 08 长任务无进度 | 已修 | 新增 `core/services/workbench/run_progress.py` 进程内进度账本；`schedule_candidate_runner.run_candidate_comparison(on_progress)` 每算完一个候选上报 (done,total)；`run_compute` → `run_worker` 串起，worker 收尾 `clear_progress`；`run_jobs._with_progress` 只在 running/computing 时附带；`RunJobAPI.js` 合同放开该形状；`RunJobControls.jsx` 渲染计数 + `role=progressbar`（有计数按百分比、无计数往返动画、reduced-motion 降级）+「计算还没结束，请不要关闭或刷新本页」；测试 `tests/workbench/test_run_progress_ledger.py` |
| 09 英文 `dependency not wired` 兜底 | 已修（本轮早段） | 29 处可见位置改 `WorkbenchTerms.outcomes.unavailable`；只在接线错误时才会抛出的开发期守卫保留原文 |
| 11 资料总览聚焦即重置 | 已修 | `MasterOverviewWorkspace.jsx` 窗口 focus 只置 `stale`，显示「切回本页后资料可能已更新…」+「刷新本页」（原地重读，保留页码 / 选中 / 详情）；`aps:master-data-changed` 仍回第 1 页；`36-analysis.css` `.mo-stale` |
| 12 工时/归属确认只有本页全选 | 已修 | `ProcessStageEditor.unconfirmed()` 按页汇总未确认工序并带 `locate_page`，`Feedback` 渲染「定位到第 N 页」；`ProcessHoursEditor` / `ProcessSourceEditor` 新增「确认全部 N 道已核对」+ 二次确认弹窗（归属编辑器只确认已选好归属 / 工种 / 供应商的行） |
| 13 「已开工工序」假控件 | 已修 | `PreflightControls.jsx:14` 改为固定说明「已开工工序：保留记录（不可修改）」，`34-run.css` `.pf-rule>.pf-fixed` |
| 14 候选甘特无图例、红色语义冲突 | 已修 | `RunCandidateGantt.jsx` 图例改为色块（安排 / 时间重叠的安排 / 外协工序），重叠不再用 critical 红；`34-run.css` `.rc-legend` |
| 17 筛选弹层任意滚动即关闭 | 已修 | `ResourceTableFilter.jsx` `scroll()` 只响应锚点自身滚动祖先的滚动，其他容器滚动不关闭 |

## P2 处理结果

### 由 P1 降级的 4 条

| # | 结果 | 说明 |
|---|---|---|
| 06 候选态缺第三页签 | 已修 | `SchedulingWorkspace.jsx` 有候选时渲染 `aria-pressed` 的「候选方案」页签 + 「不是正式计划」；L3 随之视为解决（不新增侧栏项） |
| 07 1366 双层滚动 | 未改（记录） | 需要按容器宽度而非视口重排详情面板断点，属布局专项；本轮未动，保留 finding 为 open |
| 10 页脚「预检」 | 已修 | `PreflightWorkspace.jsx:90` 改「排产检查」 |
| 15 行动区未分组 | 已修 | `RunCandidateWorkspace.jsx` 分 `rc-nav` / `rc-actions`，组间分隔线；2026-09-14 追加专项 `2026-09-14-wbui-link-button-variant`：`20-controls.css` 新增受控 `button.btn.link` 变体，两个返回按钮改为链接样式 |

### 布局与导航

| # | 结果 | 说明 |
|---|---|---|
| L1 内嵌滚动不保留 | 已修 | `WorkbenchNavigation.js` remember/restore 增加 `containers`（按 `data-wb-scroll-key`），计划中心 5 个滚动区打标；`final_foundation_navigation.cjs` 28/28 |
| L2 原型死 z-index CSS | 已修 | 在 `前端设计/ui_kits/workbench/*.css` 删除 5 条无消费者规则后重新导入快照 |
| L3 排产记录直达 | 随 06 解决 | 不新增侧栏项 |
| L4 值班台跳转标签两套命名 | 已修 | `DashboardPanels.jsx` `navigationLabels` 对齐 `navigation_metadata.py` 四组并新增 `run`；未改读 `boot.titles`（该表同时充当跳转白名单且 `outsourcing` 是页内伪视图） |
| L5 「返回排产」无条件显示 | 已修 | `BatchWorkspace.jsx` 无来源上下文时显示「下一步 · 去排产」 |
| L6 试调与现场实际甘特同图标 | 已修 | `navigation_metadata.py` 试调改 `square-pen`；`WorkbenchNavigation.js` 图标白名单与全局去重 |
| L8 试调 URL 双轨 | 未改（决定） | href 只生成 path 形式，第二种拼法不会出现在书签里，暴露面极小，不值得为此改路由 |

### 视觉与样式

| # | 结果 | 说明 |
|---|---|---|
| V1 `--wb-shadow-color` 未定义 | 已修 | `34-run.css` 改 `--ui-shadow-sm` / `--ui-shadow-md`，且被新门禁规则锁住 |
| V3 选中误用 warning 橙 | 已修（口径微调） | `.dy-analysis-bar.selected` 改 `border-color: var(--ui-primary)` + `inset 3px 0 var(--ui-card-bg)`；不用浅底是因为 `--ui-info-bg` 与 `--ui-primary-soft` 同色会抹掉选中提示 |
| V4 密度令牌边界 | 已修 | 三处自绘表 padding 改密度令牌 |
| V5 控件高度四档 | 已修 | 34px 全部改 `--wb-control-height`；新增 `--wb-control-mini-height: 30px`，mini 变体与 `.rm-actions` 统一消费 |
| V7 / 16 甘特相邻填充明度差过小 | 已修 | `.fg-plan` 改透明底 + 四边虚线，`.fg-remaining` 透明底；网格线去掉 opacity |
| V8 禁用态两套语言 | 已修 | opacity 禁用改为实色（`--ui-info-muted` / `--ui-surface-muted`） |
| V9 自托管字体单字重 | 未改（决定） | Win7 中文版自带雅黑多字重，合成加粗只在非中文或裁剪镜像出现，置信度 medium，不值得为此增大离线包 |
| V10 等宽字体栈两种写法 | 已修 | 统一 `monospace` |
| V11 死令牌 | 已修 | `typography.css` 删除 `--leading-*`；`--num-variant` 由 05 消费 |
| V12 停机窗 opacity 弱化 | 已修 | 去掉 opacity |

### 交互与文案

| # | 结果 | 说明 |
|---|---|---|
| I1 三套时间轴交互语言 | 已修（部分） | 见下文「时间轴缩放统一」；缩放上限仍由各时间轴按绘制方式（DOM / canvas）与时间跨度申报 |
| I2 收尾动词 | 已修 | 「完成确认」「完成并刷新」统一为「完成」（正式采用 / 试排采用 / 校准采用 / 值班台处置 / 外协登记），相关提示语同步 |
| I3 采用缺回退说明 | 已修 | 两个采用说明补「旧版本和报工记录都会保留…如需恢复旧安排，需要重新排产并再采用一版」，并去掉重复句 |
| I4 值班台无去排产入口 | 已修 | 候选方案列表标题区「去执行排产」 |
| I5 分类学堆叠 | 已修 | `candidate` 风险类改「候选方案待确认」；「无法评估 / 不可评估」统一「暂无数据」（含导出 CSV 与工序执行偏差表） |
| I6 同一动作两个名字 | 已修 | 按钮统一「采用方案」，词表 B 表补一行 |
| I7 行话直出 | 已修 | 「原排产候选」→「上次排产的候选方案」；「重叠拆轨 · 外协独立色」→色块图例 |
| I8 经办人每次重填 | 已修 | 新增 `WorkbenchHandlerMemory.js`（本机 localStorage 记忆，合法性校验，读写失败原因随结果返回并在输入框下方说明）；正式采用与试排采用都预填，脏检测以预填值为基线；测试 `handler_memory_probe.cjs` |
| I9 长说明密度 | 已修 | 值班台三句常驻改一句结论 + `details` 折叠 |
| I10 Choice 控件 | 已修 | 搜索行常驻、翻页改共用 `Pager`；为消除 `ResourceControls ↔ WorkbenchListControls` 循环依赖，`EmptyState` / `Pager` 的实现移到 `ResourceControls.jsx`，`WorkbenchListControls.jsx` 只保留入口名 |
| I11 工种自由文本 | 已修 | `ProcessRouteEntry.jsx` 进入时读一次 `choices('op_type')`（上限 200）渲染 `datalist`，读取失败显示错误并退回纯文本；未按归属类别过滤（录入阶段拿不到 per-row 类别） |
| I13 工艺列表空态 | 已修 | `ProcessWorkspace.jsx` `TableEmpty` 四态 + 清除筛选 |
| I14 图表刻度与空态 | 已修 | 分布图 0 / 50% / 100% 位置刻度（标计数）、空数据 `EmptyState`；趋势图补中线标签 |
| I15 分页档位不一致 | 未改（决定） | 档位由各域接口申报是 `WorkbenchListControls` 既定设计（`pager_sizes_not_declared_by_domain_api`），前端不得自造 |
| I16 SelectMenu 无搜索 | 已修 | 选项 > 8 时渲染过滤框，键入直接进过滤框；≤ 8 保留 typeahead 并把缓冲用 `role=status` 回显 |
| I18 危险确认强度 | 已修 | 删除类统一勾选「我已核对要删除的资料及其关联关系」（资源表单 / 目录编辑器）；系统管理恢复保留输入确认 |

## 时间轴缩放统一（I1 的具体做法）

- `ResourceControls.jsx` 新增 `TimelineZoom`（缩小 / N× / 放大 / 显示完整时间范围）与 `timelineZoomKey`（`+` `=` 放大、`-` 缩小、`F` 显示完整范围），计划甘特、候选甘特、值班台分析时间轴三处迁移；aria-label 统一为「缩小{范围}时间轴 / 放大{范围}时间轴 / 显示完整{范围}时间范围」。
- 候选甘特去掉与其他两处不一致的缩放滑杆（水平位置滑杆保留）。
- 现场实际甘特有「自动 / 手动」缩放模式语义，本轮未迁移。

## 有意不做或未完成的事

1. finding-07 双层滚动：已立专项 `.codestable/issues/2026-09-14-wbui-double-scroll-1366/`（报告 + 根因与 A/B/C 三方案，推荐 B），等用户拍板后实施。
2. finding-15 链接样式按钮：已于 2026-09-14 作为专项补齐（`button.btn.link` 变体），不再挂起。
3. I1 缩放上限：DOM 甘特 1024×、canvas 候选甘特 128×、值班台 64×，受绘制方式与时间跨度限制，没有统一成一个数。
4. I11 工种候选未按归属类别过滤；候选上限 200，超出部分界面说明「只提示前 N 个」。
5. `DashboardSession.js:12-13` 抛错文案保持「请不要再操作，联系维护人员」（词表第 70 行指定），不套 `outcomes.failure` 模板，因为后者的「刷新重试」与之矛盾且此时没有编号可告知。
6. 试调甘特 `.tt-bar.locked` 新增图例「已锁定，不能调整」。
7. 观察项 O1–O4 保持观察，需实机与用户拍板。

## 验证记录（2026-09-14 凌晨，最终构建 build_id 104a3249…）

按用户要求未跑全量门禁；以下全部是针对本轮触碰组件的定向验证。

| 项目 | 结果 |
|---|---|
| `node tests/workbench-app-styles.cjs`（含新增 `undefined-variable` 规则） | 0 违规 |
| `tools.scan_ui_copy`（全量 frontend） | 0 命中 |
| UI 必需组：`test_style_build_sources`、`test_ui_refinement_*`、`test_ui_copy_glossary`、`test_handler_memory`、`test_run_progress_ledger`、`test_daily_ui_refinement_opt_in`、`test_workbench_ui_registry`、`test_assets_build` | 117 通过 / 1 跳过 |
| 注册表合同 `tests/gate_meta/test_workbench_ui_registry.py` + `test_workbench_registry_contract.py` | 897 通过 |
| 纯 Node 合同：`final_foundation_navigation`（28 检查）、`batch_dashboard_return_contract`、`analysis_ui_contract`、`final_operations_context_contract`、`batch_ui_contract`、`workbench-format/terms/density/guards`、`handler_memory_probe` | 全部通过 |
| 后端定向：`test_run_progress_ledger`、候选运行器合同、run jobs / recovery、导航合同 | 通过（导航合同在重建 static 后通过） |
| 浏览器探针通道 B（排产检查 / 甘特 / 报表 / 导航 / 计划 / 点位 / 验收类，31 个文件） | 120 通过 / 5 跳过；`test_final_planning_browser` 4 个变体在更新 3 处过时断言后通过 |
| 浏览器探针通道 A（运行 / 采用 / 试排 / 值班台 / 资料总览 / 工序 / 资源 / 共享控件，30 个文件） | 69 通过 / 1 跳过；3 个失败为探针滞后于本轮改动（候选甘特缩放滑杆已去掉、按钮改名、工种输入框角色变 combobox），更新断言后复跑见下 |
| 复跑 `test_run_candidate_widgets`、`test_run_baseline_widgets`、`test_process_live_browser` | 见「复跑结果」 |
| 无 pytest 入口的组件探针 `resource_forms_probe`、`catalog_widgets_probe`（覆盖 Choice 控件与删除勾选） | 通过 |

### 复跑结果

- `test_final_planning_browser`（4 个变体）：更新 3 处过时断言后 4 通过。
- `test_run_candidate_widgets`、`test_run_baseline_widgets`、`test_process_live_browser`：更新断言后 3 通过。
- 至此本轮触碰组件的定向浏览器探针全部通过；未跑全量门禁，不构成 clean-worktree proof。

### 探针断言同步（本轮改动导致的测试更新）

- `final_planning_run_actions.cjs`：假单选「可重排」改为核对固定说明「已开工工序：保留记录（不可修改）」。
- `final_planning_plan_actions.cjs`：计划甘特缩放倍数选择器 `.plan-muted` → `.wb-zoom-level`。
- `final_planning_probe_support.cjs`：试排采用入口按钮「正式采用」→「采用方案」。
- `test_run_candidate_widgets.cjs` / `run_baseline_widgets_probe.cjs`：去掉对缩放滑杆的断言，按钮「适配完整候选时间轴」→「显示完整候选时间范围」。
- `process_live_probe.cjs`：工种输入框角色 `textbox` → `combobox`。
- 其余同步见各子代理清单（`resource_forms_probe`、`process_widgets_probe`、`dashboard_widgets_probe`、`trial_*`、`run_adoption_*`、`final_operations_*`、`el_material_actions`、`resource_live_probe`、`catalog_widgets_probe` 等）。

### 与本轮无关但在工作区可见的失败（未处理）

- `controls_browser_probe.cjs`：日期时间选择器「确定」被遗留未提交改动改成「确认」，探针未同步；HEAD 干净工作树上通过。
- `material_actions_widgets_probe.cjs`：导出文件名「物料清单完整导出.csv」被遗留改动改为「物料清单.csv」；HEAD 上通过。
- `control_style_probe.cjs`：期望 `var(--wb-control-radius)` 而 CSS 是 `var(--wb-radius-control)`，HEAD 上同样失败。
- 以上三个探针都没有 pytest 入口，不进任何门禁。

### 环境事故

- 2026-09-14 00:00 macOS 每日清理删掉了 `/tmp/aps-chromium109-assessment` 里 3 天未访问的文件，所有探针在 `newPage` 阶段 `Target crashed`。已从 npmmirror 重新安装 Chromium 109.0.5414.46（Playwright 构建 1041），备份 zip 在 `~/.cache/aps-chromium109-assessment/`；损坏包改名 `chrome-mac.broken-20260914` 留在原处。

## 追加（2026-09-14）

- 真机截图目检（隔离服务器 mixed 夹具，1280 宽，15 个视图浅色整页 + 深色首屏，0 页面错误）：甘特斜纹与成功内环在深浅两主题下可辨；资料总览「刷新本页」提示条正常；排产任务进度条（组件夹具 computing 态）深浅两主题正常；批次页「下一步 · 去排产」、排产检查页固定说明正常。
- 观察：批次管理表在 1280 宽下「优先级」列头被右侧 sticky「操作」列遮住一半，与本轮改动无关，待另行核对是否为既有问题。
- 两个专项：finding-15 链接样式按钮已实施（feature 2026-09-14-wbui-link-button-variant）；finding-07 双层滚动已立 issue 待拍板。

## 追加（2026-09-14，finding-07 方案 B 第一步）

- 用户拍板方案 B。矮屏（视口高 ≤ 820px，令牌 `--wb-short-screen-max`）下批次管理与零件工艺改成应用式布局：`.main-content` 锁 100vh 不滚，表格框 `max-height: none` 吃掉剩余高度，指标条压成一行，产能链进入节点后默认收起成一行快捷切换（可展开），内容仍放不下时 `main.page-content` 兜底滚动并带滚动记忆键。高屏布局不变。
- 改动：`00-tokens.css`、`10-shell.css`、`20-controls.css`、`21-table-frame.css`、`31-batches-resources.css`、`32-process-trial.css`、`BatchWorkspace.jsx`、`ProcessWorkspace.jsx`、`ResourceRail.jsx`、`main.jsx`；`tests/workbench/test_live_browser.py` 的 `run_probe()` 增加探针文件参数供复用。
- 新增真机测试 `tests/workbench/test_short_screen_layout.py`（8 用例通过），登记到 `WORKBENCH_UI_SUPPLEMENTAL_TESTS`；`resource_rail_probe.cjs` 矮视口两档先展开产能链再跑原断言。
- finding-07 → resolved（表格页第一步）；计划中心四个内嵌滚动区留作第二步。详见 `.codestable/issues/2026-09-14-wbui-double-scroll-1366/wbui-double-scroll-1366-fix-note.md`。
- 复跑结果（定向，未跑全量门禁）：样式门禁 0 违规；文案扫描 0 命中；注册表与样式源合同 952 通过；`test_resource_readiness` + `test_batch_widgets` + `test_process_widgets` 13 通过；`test_resource_readiness`、`test_process_live_browser`、`test_resource_live_browser`、`test_process_readiness_browser`、`test_ed_material_process_browser`、`test_el_material_browser`、`test_ui_navigation_guard` 18 通过 2 跳过（两处 opt-in）；`test_ui_refinement_geometry` 1 通过；新增 `test_short_screen_layout` 1 通过（8 用例）。
- 打开 opt-in 开关（`ED_RUN_BROWSER=1` / `EL_RUN_BROWSER=1`）后两个物料真机验收失败，在 HEAD 干净工作树上复跑同样失败、原因一致（`el_material_actions.cjs` 用精确文本等 `第 2 / 2 页`，而分页器摘要是一整段 `共 25 项 · 第 2 / 2 页`；`ed_material_process_visual.cjs` 的文字裁切检查把 `.wb-visually-hidden` 表格标题当成被裁切文字，20 例失败），属既有失败，与本轮无关，未处理。

## 追加（2026-09-14，两个 opt-in 物料验收测试修复 + 执行通道）

- 根因：两项测试自 09-10 起只在 `ED_RUN_BROWSER=1` / `EL_RUN_BROWSER=1` 下执行，门禁只收集后跳过；09-13 界面重做（`1a7a75c6`）后没人跑过，累计了五类过期假设：共享分页器把摘要合成一句、`.pager` 改名 `.wb-pager` 且每页选项文案变为「20 项」、取消已修改表单会先弹「离开前确认」、`?view=process` 会恢复上次节点与上次打开的详情弹窗、共享空态标题改为「当前筛选没有匹配项」。另外 ED 的文字裁切检查把无障碍隐藏标题当成缺陷，并因用例中途抛错让弹窗残留而级联 17 例。
- 探针修正：`el_material_actions.cjs`（分页器整句匹配、`.wb-pager`、取消后点「放弃未保存内容并继续」、空态标题）；`ed_material_process_visual.cjs`（跳过 `.wb-visually-hidden` / `clip: rect(0,0,0,0)` 节点）；`ed_material_process_probe.cjs`（失败后 `recover`：Escape 关残留弹窗，关不掉则刷新）；`ed_material_process_stages.cjs`（进入工艺页前关掉被恢复的详情弹窗）；`ed_material_process_states.cjs`（显式点物料节点再搜索）；`ed_material_process_filters.cjs`（「20 项」、`.wb-pager`）。
- 产品修正一处：`ProcessDetail.jsx` 已就绪工序汇总表列宽 `[14,10,8,18,10,10,10,20]` → `[11,9,8,16,13,13,11,19]`，「换型工时（小时）」「单件工时（小时）」表头在 1078px 宽表里原本被裁掉约 4px，这是裁切检查抓到的真问题。
- 新增 `scripts/run_workbench_opt_in_browser.py`：解析 opt-in 分组各测试文件里的开关并全部打开，跳过不算通过（退出码 3），报告落 JSON；用法见 `.codestable/reference/tools.md` 第 4 节，教训见 `.codestable/compound/2026-09-14-learning-opt-in-browser-tests-rot.md`。
- 验证：`run_workbench_opt_in_browser.py --only material` 2 通过（ED 28/28 用例、EL 全部用例，约 5 分钟）；`test_process_widgets` 1 通过（列宽调整无回归）。整条 opt-in 通道的其余 8 项本轮没有跑，是否同样腐烂未知。

## 追加（2026-09-14，opt-in 通道其余 8 项：找到并修）

用 `scripts/run_workbench_opt_in_browser.py` 把 `workbench_browser_opt_in` 分组其余 8 项全部打开开关实跑，4 项一次通过（`test_process_stage_live_browser`、`test_modal_focus_browser`、`test_asset_browser_globals`、`test_reports_review_browser`、`test_merged_cycle_ui`），3 项失败并已修：

- `test_az_contrast_modal_scroll`（对比度 + 弹窗滚动，组件夹具）与 `test_secondary_copy_contrast`（组件部分）：共用的 `az_contrast_modal_harness.cjs` 只列了 11 个源码文件，09-13 之后被挂载的组件要读 `WorkbenchTerms` / `WorkbenchFormat` / `WorkbenchControls` 等新全局，页面报 `Cannot read properties of undefined`（81 条）。按 `build-order.json` 的 live 顺序算出 29 个文件的依赖闭包写回 `appFiles`。
- `az_contrast_probe.cjs`：次要文案颜色原来写死 `rgb(96, 112, 135)`，令牌 `--ui-info-muted` 已在 09-13 改为 `#475569` 提高对比度；改为在页面里解析 `--wb-secondary-copy` 令牌再比对，对比度 ≥ 4.5 的断言保留。
- `az_modal_scroll_probe.cjs` 揪出一处真问题：`21-table-frame.css` 给所有 `.wb-table-frame` 加了 `overscroll-behavior: contain`，弹窗里的预检表格滚到底后滚轮不再传给弹窗正文，光标停在表格上时永远够不到底部按钮。产品修正：`.modal-b .wb-table-frame { overscroll-behavior: auto }`；探针改为直接在嵌套表格上滚轮并断言链式滚动，同时断言该属性为 `auto`。页面级表格框的 `contain` 保留（Chromium 109 实测：不可滚动的短表格不会吞掉页面滚轮）。
- `test_migrated_process_batch_browser`（迁移工艺批次，单状态 22 例）：回执恢复用例靠 CDP 把下载限速到 16 B/s 等 200 响应头，现在响应头本身就超过 15 秒等待，改为与 ED 探针相同的「响应阶段 `Fetch.failRequest` 断连」；恢复后的完成文案跟随现行文案；批次工序工时文案改为 `换型 0.5 小时 / 单件 1.375 小时`（数值各带单位）；数据变更白名单补上批次写入现在同步产生的派生表（`WorkbenchDashboardItems`、`WorkbenchOutsourcingOperationOrigins`、`WorkbenchTemplateLineageEvents` / `Origins`），所有者按 `batch_id` → `batch_ref`（实体引用）→ `operation_ref`（计划来源引用 `alternate_key`）回溯到 `AN-` 批次，自增序列白名单加 `WorkbenchTemplateLineageEvents`。
- 最终整条通道复跑：`run_workbench_opt_in_browser.py` 10 个测试文件 39 个用例全部通过、0 跳过，用时 21 分 56 秒（迁移工艺批次 4 个状态、物料两项、工艺阶段真机等都在内）。报告 JSON 与日志在运行时打印的 `OPT_IN_BROWSER_LANE report=` 路径下。
