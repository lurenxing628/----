---
doc_type: audit-index
audit: 2026-09-13-frontend-ui-ux-review
scope: 现行工作台前端（frontend/workbench/app 源码及其构建产物）样式、布局、配色、交互、认知负担只读审查
created: 2026-09-13
reviewed: 2026-09-14
status: active
remediation: remediation-record.md
total_findings: 50
open_findings: 0
resolved_findings: 46
partially_resolved: 1
decided_no_change: 3
withdrawn_findings: 3
covered_by_existing_decisions: 2
observations: 4
subagents_used: 8
---

# 现行前端 UI/UX 审计报告

## 整改状态（2026-09-14）

P1 12 条与 P2 38 条已按 [remediation-record.md](remediation-record.md) 实施：46 条已修（含 finding-07 按方案 B 完成表格页第一步，见 `.codestable/issues/2026-09-14-wbui-double-scroll-1366/`）、1 条部分修复（I1）、3 条经裁决不改（L8、V9、I15）。观察项 O1–O4 未动。验证为定向验证，未跑全量门禁。

**独立复核（2026-09-14，非修复方自查）**：[verification-2026-09-14.md](verification-2026-09-14.md)——4 个只读验证代理逐条核对源码与构建产物，确认修复真实落地、产物同步无交付风险；另列出 12 条卫生级尾巴（R1–R12，如词表 allow 表未闭环、3 处散文「无法评估」、`34-run.css:33` 残留透明度禁用等），无新增缺陷。

## 范围

审查对象是**现行前端**（2026 年重做后的 React 18 SPA），不含 `前端设计/` 与 `static/workbench/prototype/` 旧资料（prototype 仅作为现行样式的令牌基底来源被追踪）：

- 壳层与导航：`templates/workbench/index.html`、`frontend/workbench/app/main.jsx`、`WorkbenchNavigation.js`、`WorkbenchPageContext.js`、`WorkbenchBoundary.jsx`、`WorkbenchDensity.js`、`WorkbenchScrollShadows.js`、`web/routes/workbench/navigation_metadata.py`
- 样式：`frontend/workbench/app/styles/` 全部 17 个 CSS、`theme.js`、`frontend/workbench/prototype/tokens/*.css`、`prototype/ui_kits/workbench/gantt-theme.css`
- 核心排产流程：Dashboard*、Preflight*、RunJob*、RunCandidate*、RunAdoption*、PlanCatalog / PlanDetails / PlanGantt / PlanSelection、Batch*、Trial* 共 22+ 模块逐文件阅读
- 基础数据与辅助工作区：Resource*、Process*、Field*、MasterOverview*、Review* / Report*、System*，以及共享控件 WorkbenchDatePicker / WorkbenchSelectMenu / WorkbenchDetailPanel / CalendarRangeDialog
- 渲染证据：`evidence/workbench-ui/2026-09-12-final/` 实机截图，以整改后的 `browser-e696/`（09-12 21:48）为现状依据

首轮审查（4 个只读代理）于 2026-09-13 21:39 完成；同日复核（4 个只读代理 + 主代理）逐条核对了全部发现，本文件与各 finding 已按复核结果改写。复核只读源码、复算对比度、查看截图，未起浏览器实跑；finding-09 的处置跑了 5 个测试文件。

## 总体结论

这套前端的**工程底子明显高于一般企业前端**：颜色 100% 走令牌（17 个 CSS 0 处裸 hex、0 处 rgba()）、暗色主题纯令牌重映射零特判、font-size 与 z-index 零硬编码、93 处 `!important` 全部集中在 `20-controls.css`；危险操作全是「预检 → 确认 → 回执」两段式；「未知不按零显示」的不确定性表达在工业软件里属上等水平；工作区状态可保存恢复、脏表单有离开守卫、焦点管理规范。

**问题不在骨架，在三层打磨**：

1. **视觉细节**：甘特红绿状态色盲不可辨（明度比 1.02–1.15）、现场实际甘特的实际条与计划基线条明度比 1.002、暗色表格 hover 零反馈、现场时间线计划条 1.36:1、数字未全局等宽。
2. **交互一致性**：三套时间轴三种交互语言、候选甘特无图例且红色语义与计划甘特冲突、危险确认强度不统一、列筛选弹层一滚就关。
3. **认知负担**：排产长任务只有耗时没有进度、工时确认只能本页全选、资料总览切窗即重置、候选态缺显式页签。

共 50 条有效发现：P1 × 12（逐条见 finding-NN.md，其中 finding-09 已在工作区修复）、P2 × 38（本文件汇总表，4 条由 P1 降级并保留 finding 文件）。另有 4 条观察项、3 条撤销、2 条已被既有决定覆盖，均留档在文末。无 P0。

## 证据强度说明

- **坐标口径**：全部指向源码 `frontend/workbench/app/*.jsx|*.js`、`frontend/workbench/app/styles/*.css`、`frontend/workbench/prototype/`，以及 `web/`、`core/`、`data/`、`tests/`。行号以 2026-09-13 复核时的工作区为准：HEAD 035f9cce 之上含一份遗留的未提交前端文案改动，以及本轮 finding-09 的处置。CSS 与原型令牌文件在 HEAD 与工作区字节一致。`static/workbench/` 是构建产物，不作为引用对象。
- **截图口径**：现状证据用整改后的 `evidence/workbench-ui/2026-09-12-final/browser-e696/`（09-12 21:48）；`baseline-current/`（09-12 13:22）是整改前的图，侧栏仍为旧 14 项，只作前后对比。夹具数据名（`adopted label`、`Isolated run fixture …`、`Catalog part`）是隔离环境标识，不计为缺陷。
- **对比度**：全部按 WCAG 相对亮度公式复算并与首轮数字并列；红绿色盲模拟值仓内无矩阵实现，未复核，只作参考。
- **既有决定**：每条都对照了 `.codestable/roadmap/workbench-ui-refinement/`（25 条，24 done）与文案词表裁决 `.codestable/compound/2026-09-13-decision-ui-copy-glossary.md`，结论见下一节。
- 夹具数据仅 15 分钟窗口、3 道工序，甘特条在大数据量下的拥挤表现未实测。

## 对照既有决定

| 既有决定 | 关联发现 | 关系 |
|---|---|---|
| `wbui-view-tabs-merge`（入口 + 页内页签，侧栏 12 项） | finding-06、P2-L3 | 三态结构是其产物；不得再加侧栏项 |
| `wbui-nav-boot-groups`（图标按组去重） | P2-L6 | 跨组同图标是既定口径，只能作全局去重提案 |
| `wbui-viewport-budget`（1280 视口合同，几何断言 G1–G4） | 观察项 O3 | 1280 / 1366 已过门禁 |
| `wbui-prototype-css-cleanup`（先量再删原型 CSS） | P2-L2、P2-V11 | 死 CSS / 死令牌是其漏项；删除须经 `前端设计/` 快照通道 |
| `wbui-empty-loading-pager`（EmptyState / Pager 接入全部列表页） | P2-I10、P2-I13；撤销的 L9 | I10 / I13 是其验收漏项；L9 误把 `kind="loading"` 档位当顶替 |
| `wbui-r2-empty-height-reason-copy`（工具栏 tooltip、页面级主动作 inline） | 撤销的 I17 | 有意设计 |
| `wbui-table-density-noise`（密度绑定共享表格框） | P2-V4 | 覆盖边界是既定设计，可作扩展提案 |
| `wbui-r2-token-wiring`（保留字面量待专项收敛） | 已覆盖的 V6 | accepted deferral |
| `wbui-tokens-states`（字号整数分档） | 观察项 O1 | 13px 是已定分档，改档要重新拍板 |
| `wbui-run-stepper`（候选页只留「采用方案」实心） | finding-15、P2-I6 | 主按钮层级已处理；「采用为正式计划」会引入第三个名字 |
| 词表裁决 :28 / :92 / :93（预检、排产检查） | finding-10 | 原建议与裁决相反，已改写 |
| 词表裁决 :56（排产记录） | finding-06 | 标题是裁决产物 |
| 词表裁决 :67（接入 → 尚未开通，开发期守卫不得显示） | finding-09 | 处置依据 |
| 词表裁决 :70 / :146（保留现场文案、程序出错模板） | P2-I2 | 原「温度过硬」半句撤销 |
| 词表裁决 :87 / :88 与 B 表「没有值」行 | P2-I5、P2-I7 | 「不可评估」应为「暂无数据」 |
| 词表裁决 :102（侧栏改名） | P2-L4 后半 | 已覆盖 |

## 发现清单（P1）

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | usability | P1 | high | 甘特条「冲突/超期」与「成功/锁定」仅靠红绿 pastel 填充区分，色盲不可辨 | [finding-01.md](finding-01.md) |
| 2 | usability | P1 | high | 暗色主题表格行 hover 色与卡片底色完全相同，悬停零反馈 | [finding-02.md](finding-02.md) |
| 3 | bug | P1 | high | 排产来源切换按钮选中态样式静默失效，引用三个不存在的令牌 | [finding-03.md](finding-03.md) |
| 4 | usability | P1 | high | 现场工序详情时间轴「计划」条对比度 1.36:1，近隐形 | [finding-04.md](finding-04.md) |
| 5 | usability | P1 | high | 排产数字未全局等宽，`--num-variant` 令牌零消费 | [finding-05.md](finding-05.md) |
| 8 | usability | P1 | high | 排产长任务无进度指示，且契约把 progress 钉死为 null | [finding-08.md](finding-08.md) |
| 9 | usability | P1 | high | 未提交改动把英文 `dependency not wired` 当界面兜底文案（已在工作区修复） | [finding-09.md](finding-09.md) |
| 11 | bug | P1 | high | 资料总览页窗口聚焦即整表重置 | [finding-11.md](finding-11.md) |
| 12 | usability | P1 | high | 工时/归属确认仅「本页全选」，服务端协议本是整零件粒度 | [finding-12.md](finding-12.md) |
| 13 | bug | P1 | high | 「已开工工序」规则是永远改不了的假控件 | [finding-13.md](finding-13.md) |
| 14 | usability | P1 | high | 候选甘特无颜色图例，且红色语义与计划甘特冲突 | [finding-14.md](finding-14.md) |
| 17 | usability | P1 | high | 列筛选弹层在任何非弹层内滚动时关闭，未应用的勾选丢失 | [finding-17.md](finding-17.md) |

## P2 汇总表

### 由 P1 降级（保留 finding 文件）

| # | 标题 | 说明 |
|---|---|---|
| 6 | 「选择排产方案」入口承载三态，候选态缺显式页签、侧栏高亮只看 view | [finding-06.md](finding-06.md)；页内「计划版本 / 排产记录」页签一直在，缺的是第三个 |
| 7 | 1366×768 上表格内滚与窗口滚动并存的双层滚动 | [finding-07.md](finding-07.md)；详情面板断点按视口算，1366 仍并排 |
| 10 | 排产检查页页脚仍写「预检」 | [finding-10.md](finding-10.md)；三道关卡各有专名，残留只剩一处 |
| 15 | 候选工作区行动区导航类与动作类按钮无分组并列 | [finding-15.md](finding-15.md)；主按钮层级已由 `wbui-run-stepper` 处理 |

### 布局与导航

| # | 标题 | 关键证据 |
|---|---|---|
| P2-L1 | 内嵌滚动位置不保留：切走再切回表格 / 甘特视口复位 | `WorkbenchNavigation.js:92-104` remember 只存 windowTop/Left 与 mainTop/Left，`:134-141` restore 同；计划中心 4 个内嵌滚动区 `33-gantt-foundation.css:48,67,106,110` |
| P2-L2 | 原型弹层 z-index 死 CSS 残留（清理项） | `prototype/ui_kits/workbench/dashboard-workbench.css:133`(60)、`trial-sample.css:176`(80)、`field-reporting.css:86`(5000)、`batch-workbench.css:82,85`(79/80) 仍随构建下发，但选择器在现行 JSX 0 消费者；现行弹层已在 `21-table-frame.css:69-72` 重映射到 `--wb-z-*`。无层叠风险，挂 `wbui-prototype-css-cleanup` 漏项 |
| P2-L3 | 「排产记录」无侧栏直达入口 | `navigation_metadata.py:14` 排产组无该项；入口是 `SchedulingWorkspace.jsx:49,71` 的页内页签。修法不得新增侧栏项，见 finding-06 |
| P2-L4 | 值班台跳转标签与侧栏两套命名 | `DashboardPanels.jsx:4` navigationLabels 与 `navigation_metadata.py:4-8` 四组不一致：批次资料 / 批次管理、候选方案 / 选择排产方案、现场报工 / 现场记录、现场实际 / 现场实际甘特。应改读 boot.titles |
| P2-L5 | 批次管理「返回排产」按钮无条件显示 | `BatchWorkspace.jsx:119` 无来源上下文时兜底 `'run'`，`:143` onNav 存在即渲染，侧栏直入时「返回」语义错位 |
| P2-L6 | 「试调」与「现场实际甘特」共用 gantt 图标 | `navigation_metadata.py:14-15`；`WorkbenchNavigation.js:29` 图标去重按组，跨组同图标是 `wbui-nav-boot-groups` 既定口径，本条为全局去重提案 |
| P2-L8 | 试调 URL 双轨 | `pages.py:74` trial_url 与 `WorkbenchNavigation.js:53-54` 同时接受 path 与 `?view=trial`；但 `:78` href 只生成 path 形式，书签不会出现第二种拼法，暴露面极小 |

### 视觉与样式

| # | 标题 | 关键证据 |
|---|---|---|
| P2-V1 | `--wb-shadow-color` 全仓未定义 | `34-run.css:31,124` 两处 `var(--wb-shadow-color, var(--ui-border))` 回退为 1.23:1 边框色；阴影仍渲染，属令牌卫生。`36-analysis.css:73` 直接写 `--ui-border`，不属回退 |
| P2-V3 | 「选中」指示误用 warning 橙 | `36-analysis.css:71` `.dy-analysis-bar.selected` outline 用 `--ui-warning-text`；同仓选中语言是 `inset 3px 0 var(--ui-primary)`（`33-gantt-foundation.css:156`、`32-process-trial.css:83`），单点孤例 |
| P2-V4 | 密度令牌覆盖边界 | `00-tokens.css:46-49` 由 `20-controls.css:427`（`table.wb-table`，38 个 JSX 文件共用）、`35-field.css:20`、`37-reports.css:108` 消费；自绘表 `32-calendar-outsourcing.css:10`、`36-analysis.css:28`、`34-run.css:71` 硬编码 padding。边界是 `wbui-table-density-noise` 既定设计，本条为扩展提案 |
| P2-V5 | 控件高度四档并存 | `20-controls.css:3-4`（32 / 36 令牌）；34px 见 `32-calendar-outsourcing.css:36`、`35-field.css:5`、`36-analysis.css:26`、`33-gantt-foundation.css:112`；30px 中 `20-controls.css:85` mini 为有意变体，漂移的是 `32-calendar-outsourcing.css:90`、`32-process-trial.css:119`、`31-batches-resources.css:76` |
| P2-V7 | 甘特相邻填充明度差过小 | `33-plan-gantt.css:26-28` primary-fill vs reference-fill 1.137；`33-gantt-foundation.css:161` 网格线 opacity .6 后 1.132 |
| 16 | 现场实际甘特实际条与计划基线条填充明度比 1.002 | [finding-16.md](finding-16.md)；`gantt-theme.css:7,14`，`33-plan-gantt.css:26-28`，靠色相与虚线边区分 |
| P2-V8 | 禁用态两套语言并存 | `20-controls.css:128` 实色 vs `31-batches-resources.css:83,124`、`35-field.css:12` opacity（styles 内 .5 / .55 / .65 三档） |
| P2-V9 | 自托管字体仅 400 单字重 | `prototype/tokens/typography.css:14-21` 仅 400，`:43-46` 声明 500 / 600 / 700；字体栈（`:23-25`）把 Segoe UI 与系统雅黑放前，Win7 中文版自带雅黑，合成加粗只在非中文或裁剪镜像出现，置信度 medium |
| P2-V10 | 等宽字体栈两种写法 | `31-batches-resources.css:127`、`32-process-trial.css:72`（monospace）vs `34-run.css:96`（ui-monospace,monospace）；Chrome 109 不支持 ui-monospace，渲染一致，纯代码卫生 |
| P2-V11 | 死令牌 | `typography.css:49-52` `--leading-*` 与 `:55` `--num-variant` 零消费属实；原列 `--badge-*`（8 处消费）、`--gantt-normal`（`colors.css:66`，3 处消费）、`colors.css:56` 不是死令牌，撤。删除须经 `前端设计/` 快照通道 |
| P2-V12 | 停机窗 danger 底 + opacity .75 弱化 | `36-analysis.css:68` 填充叠 opacity 后 1.07，但 1px dashed `--ui-danger-text` 边叠后仍 4.25:1，语义可辨；观感建议 |

### 交互与文案

| # | 标题 | 关键证据 |
|---|---|---|
| P2-I1 | 三套时间轴交互语言不一致 | `PlanGantt.jsx:31,72,98-99,112-114`（1–1024×、+ / - / = 快捷键）、`:149-152` 7 项图例；`RunCandidateGantt.jsx:79,105-108`（1–128×、滑杆、无缩放快捷键）；`DashboardTimeline.jsx:5,25-26`（1–64×、无键盘）。三个缩放上限 |
| P2-I2 | 收尾动词不一致 | `RunAdoptionControls.jsx:34`「完成确认」vs `DashboardHandling.jsx:21`「完成并刷新」；另 `DashboardSession.js:12-13` 抛错未用 `WorkbenchTerms.outcomes.failure` 三段式模板。「请不要再操作，联系维护人员」是裁决第 70 行指定文案，不改 |
| P2-I3 | 采用确认缺回退说明 | `RunAdoptionControls.jsx:8` 只说保留旧版；后端无回退能力（见 remediation-plan 2.11），文案只能写「旧版可查看导出，恢复需重新排产再采用」 |
| P2-I4 | 值班台无「去排产」直达入口 | `DashboardPanels.jsx:4` navigationLabels 无 run / preflight 目标 |
| P2-I5 | 分类学堆叠，「候选方案」跨两套分类 | `PlanCatalogUI.jsx:7` 4 种计划类型；`DashboardContract.js:4-5` 7 类风险 + 4 种处置状态；另 `DashboardContract.js:6`「无法评估」与 `TrialControls.jsx:5`「不可评估」同概念两写法，按裁决应为「暂无数据」 |
| P2-I6 | 同一动作两个名字 | `RunAdoptionAction.jsx:106`「采用方案」vs `TrialAdoptionAction.jsx:7`、`TrialWorkspace.jsx:127`「正式采用」；裁决未定按钮名，需补一行；不引入「采用为正式计划」 |
| P2-I7 | 行话直出 | `TrialControls.jsx:5`「不可评估」、`:6`「原排产候选」、`RunCandidateGantt.jsx:110`「重叠拆轨 · 外协独立色」 |
| P2-I8 | 经办人每次重填并重新解释 | `RunAdoptionAction.jsx:3`、`TrialAdoptionState.js:35,133` 初值与完成后均清空；`TrialAdoptionControls.jsx:15-17` 硬编码「经办人」与另一套说明语，绕开 `WorkbenchTerms.handler`。可复用 `TrialViewState.js:3-45` 偏好模式；后端 `core/models/workbench_run_adoption.py:32-35` 只校验非空、≤100、无 NUL |
| P2-I9 | 长说明密度过高 | `DashboardPanels.jsx:87` 三句常驻；候选页 `RunCandidateWorkspace.jsx:138` 已是 details 折叠，不在此列 |
| P2-I10 | Choice 关联选择控件 | `ResourceControls.jsx:290` 放大镜切换搜索、`:272-275` 搜索框默认隐藏、`:240` size 50 固定、`:291-292` 裸 chevron 翻页未用 Pager |
| P2-I11 | 工艺路线工种是自由文本 | `ProcessRouteEntry.jsx:88` 纯 text input，兜底只有 `ProcessContract.js:123-139` 的预检诊断 |
| P2-I13 | 工艺列表空态是纯文本 | `ProcessWorkspace.jsx:53` 裸 td 文本，无 filtered 态无清除筛选；对照 `ResourceTables.jsx:86` 的 EmptyState 四态。`wbui-empty-loading-pager` 验收漏项 |
| P2-I14 | 图表刻度与空态 | `ReviewChartViews.jsx:3-8` 分布图无轴刻度、空数据渲染空 ul；`:18` 趋势图带标签刻度只有 0 与 max（`:21` 另有无标签中线，`:11` 有 EmptyState，`:26` 有数据表） |
| P2-I15 | 分页 size 档位不一致 | 5 个可变族：[20,50,100] × 5 处、[10,25,50] × 2、[10,20,50] × 3、[10,20,50,100] × 2、[2,10,20,50,100] × 1，另 4 种固定档；`WorkbenchListControls.jsx:23-24` 要求档位由各域接口申报，属既定设计，可统一的只有纯前端分页处 |
| P2-I16 | SelectMenu 无搜索框、键入缓冲不可见 | `WorkbenchSelectMenu.jsx:11,40-48` 无搜索框，typeahead 缓冲 700ms，无回显 |
| P2-I18 | 危险操作确认强度不统一 | `SystemMaintenanceControls.jsx:38` 恢复需输入「恢复」，`:37` 删备份仅勾选；`ResourceForms.jsx:127,129`、`ResourceCatalogEditor.jsx:61` 删基础资料仅文字确认。P1 边缘 |

## 观察项

| # | 内容 | 说明 |
|---|---|---|
| O1 | 表格正文 13px / 辅助 12px 是否偏小 | `20-controls.css:429`、`typography.css:31-35`；设计判断，`wbui-tokens-states` 已定分档，需实机与用户拍板 |
| O2 | 方案名直接显示内部 label 原文 | 截图夹具中 `adopted label` 等字样；无代码位置，待核 |
| O3 | 1920 宽屏留白、1280 现场甘特工具栏拥挤 | 仅截图印象，无违反几何合同 G1–G4 的数字；`wbui-viewport-budget` 已过门禁 |
| O4 | warning 3px 左边条对比度 3.045 | 8 处（`34-run.css:48,64,89,109,150,167`、`32-process-trial.css:110`、`37-reports.css:127`；`11-navigation.css:52/58`）通过 3:1 阈值，余量小 |

## 撤销与覆盖记录

| 原编号 | 结论 | 依据 |
|---|---|---|
| P2-L7 ≤900px `.nav-label` 未隐藏 | 不成立 | `prototype/ui_kits/workbench/operations-workspaces.css:8-13` 已隐藏；首轮只读了 app 层 |
| P2-L9 加载态用 EmptyState 顶替 | 不成立 | `kind="loading"` 是正式档位（`WorkbenchListControls.jsx:5-8`） |
| P2-I17 禁用原因展示不一致 | 已覆盖 | `wbui-r2-empty-height-reason-copy` 有意设计，`ResourceControls.jsx:21` 注释写明 |
| P2-V6 间距 / 行高硬编码 | 已覆盖 | `wbui-r2-token-wiring` 记录「保留字面量，待专项收敛」；复算 329 / 32 处 |
| P2-L4 后半「基础资料」vs「资料总览」 | 已覆盖 | 词表裁决第 102 行 |
| 原 finding-07 前提「1366 恒处详情下排」、原 finding-10 前提「同一关卡三名」 | 前提不成立 | 已改写，见对应 finding |

## 按维度分布

| 性质 | P1 | P2 | 合计 |
|---|---:|---:|---:|
| bug（功能性缺陷） | 3 | 0 | 3 |
| usability（可用性 / 可访问性 / 文案） | 9 | 38 | 47 |
| **合计** | **12** | **38** | **50** |

说明：本轮为 UI/UX 专项审查，`nature` 在 cs-audit 模板的 bug / security / performance / maintainability / arch-drift 之外扩展了 `usability`；security / performance 不在范围。置信度除 P2-V9 标 medium 外均为 high，指代码事实可核实；影响程度的判断见各条「影响」。

## 做得好的地方（修复时不要破坏）

1. 颜色令牌治理样板级：0 裸 hex / 0 rgba()；暗色主题纯令牌重映射，新增组件天然双主题。
2. 语义色四档（ok / notice / warning / danger）+ 每档 bg / border / text / muted 四件套，文字对比度全过 WCAG AA。
3. 危险操作确认链完整：采用前强制预检 → 弹窗明示范围与后果 → 原因 + 经办人 + 勾选核对 → 回执；恢复备份需手输「恢复」。
4. 诚实的不确定性表达：「处置数量未知，这里不会按零显示」「未排不代表改善」。
5. 每工作区状态独立保存恢复；脏数据离开守卫覆盖侧栏 / 前进后退 / 外链。
6. 焦点管理规范；计划 tab 条完整键盘支持；`prefers-reduced-motion` 降级。
7. 技术性错误信息由 `WorkbenchReferences.jsx` 自动折进「原始错误信息」，用户只看友好句。
8. 甘特非颜色线索已有苗头（图例虚线边、今日下划线、选中 inset 色条、基线条虚线边），色盲修复应顺这套语言扩展。
9. 93 处 `!important` 集中单文件且逐条带 override 注释。
10. 壳层错误处理面向非技术用户：启动 15s 超时兜底、boot 校验失败安抚文案、渲染崩溃给「重新打开此工作区」而非白屏。

## 下一步建议

修改建议方案见同目录 [remediation-plan.md](remediation-plan.md)，按四个阶段组织：

- **阶段 0 · Quick wins**（finding-02 / 03 / 05 / 13 / 10、P2-V1；finding-09 已完成）
- **阶段 1 · 术语与文案**（与词表裁决对齐后的替换表）
- **阶段 2 · 交互修复**（finding-01 / 04 / 06 / 11 / 12 / 14 / 15 / 16 / 17 + P2-I3 / I4 / I10 / I13 / I18）
- **阶段 3 · 布局与组件**（finding-07 + P2-L1 / L2 / V4 / V5 / V11 / I1）
- **阶段 4 · 需后端配合**（finding-08 排产进度）

## 复核记录（2026-09-13）

首轮报告的四类系统性问题及处理：

1. **坐标指向构建产物**：JS 行号原指 `static/workbench/app/*.js`，且 static 由未提交改动重建；已全部换成源码坐标，CSS 与 .py 中 4 处独立错行也已更正。
2. **未对照既有决定**：新增「对照既有决定」一节；3 条撤销、2 条已覆盖、多条改写。
3. **截图集合与断言不符**：现状证据改用 `browser-e696/`；finding-04 的截图佐证撤销。
4. **严重度一刀切**：finding-06 / 07 / 10 / 15 降 P2，P2-I12 升 P1（finding-17），P2-V2 转观察项；P2-V9 置信度 medium。

复核新增：finding-16（甘特实际条 vs 计划基线条 1.002）、finding-17（列筛选弹层滚动即关）；finding-09 重新归因为未提交改动引入的回退并已处置。首轮 P2 表实际列了 40 条而自称 39 条，本版计数以本文件表格为准。
