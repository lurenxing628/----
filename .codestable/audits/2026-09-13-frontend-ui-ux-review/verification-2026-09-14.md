---
doc_type: audit-verification
audit: 2026-09-13-frontend-ui-ux-review
created: 2026-09-14
verifier: 独立复核（4 个只读验证代理 + 主代理抽查），非修复方自查
scope: P1 15 条 + P2 40 条（含复核新增 finding-16/17）在当前工作区代码（HEAD 035f9cce + 未暂存改动）的修复状态
status: completed
---

# 前端 UI/UX 审计修复 · 独立复核记录（2026-09-14）

复核口径：以 `frontend/workbench/app/`（源码）为准，`static/workbench/app/`（运行时装载的构建产物）逐条核对同步。对照修复方自述 [remediation-record.md](remediation-record.md)。本复核为只读，未跑测试套件；修复方的定向验证结果见其记录。

## 结论一句话

**修复真实落地，质量高于自述口径**——55 条发现中独立确认 40 条已修复、6 条部分修复、4 条裁决不改、3 条复核撤销原判、1 条观察、1 条未复核；static 产物与源码同步，无「源已修产物仍旧」的交付风险。另发现 12 条修复尾巴/新残留，全部为卫生级或记录在案的取舍，无新增缺陷。

## P1 逐条状态（15 条）

| # | 发现 | 独立复核状态 | 关键新证据 |
|---|---|---|---|
| 01 | 甘特红绿色盲 | ✅ 已修复 | `00-tokens.css:25-27` 新增斜纹/内环保底三通道；`33-gantt-foundation.css:87-90`、`32-process-trial.css:91-95`、`33-plan-gantt.css:18-19` 消费；RunCandidateGantt.jsx:35-39 canvas 斜纹；复算斜纹 vs 底 3.49:1（浅）/4.30:1（暗） |
| 02 | 暗色 hover 零反馈 | ✅ 已修复 | `dark.css:34` hover `#334155` ≠ 卡片 `#1e293b`（1.41:1） |
| 03 | 排产来源选中态死 token | ✅ 已修复 | `34-run.css:158` 改用 info-text/info-bg/primary；旧三死 token 全仓零引用；**新增 `undefined-variable` 样式门禁规则防回潮** |
| 04 | 现场 planned 条隐形 | ✅ 已修复 | `35-field.css:15` 保留浅填充 + 深色内描边（浅色 6.41:1 / 暗色 11.49:1） |
| 05 | 字号偏小 + 数字不等宽 | 🟡 部分修复 | 等宽已全局：`20-controls.css:436` 全表 `tabular-nums`；字号阶梯 12/13/14 未调（裁决观察项 O1，非遗漏） |
| 06 | 计划中心一名三态 | 🟡 部分修复 | 候选态新增 `aria-pressed`+`aria-current` 第三页签 +「不是正式计划」（`SchedulingWorkspace.jsx:72-73`）；排产记录态侧栏高亮仍与页头标题不一致（记录在案接受）；未新增侧栏项（L3 随之关闭） |
| 07 | 1366×768 双层滚动 | 🟡 部分修复 | 方案 B 第一步落地：矮屏 ≤820px 批次/工艺改应用式布局（`00-tokens.css:9`、`10-shell.css:70-77`、`21-table-frame.css:74-77`）；**计划中心 4 个内嵌滚动区未动，留作第二步**（issue `2026-09-14-wbui-double-scroll-1366`） |
| 08 | 长任务无进度 | ✅ 已修复 | 前后端打通：`run_progress.py` 账本 + `RunJobControls.jsx:14-19`「已算完 X/Y 个候选方案」+ role=progressbar + 常驻「请不要关闭或刷新」+ 切页暂停升级为醒目条 |
| 09 | dependency not wired 上屏 | ✅ 已修复 | 用户可见位置 0 处；统一 `WorkbenchTerms.outcomes.unavailable`「此功能尚未开通。」；剩余 30 处/20 文件全为开发期守卫 throw，且 `WorkbenchReferences.jsx:13-28` 把技术信息折进「原始错误信息」折叠区；未走 console 是因探针合同要求页面零 console 错误 |
| 10 | 检查/排产检查/预检三名 | ✅ 已修复（带 1 条词表尾巴） | 三道关卡各用专名（排产前=排产检查、采用前=预检），词表入门禁 `ui_copy_glossary.json:311-317`；尾巴见 R1 |
| 11 | 资料总览 focus 重置 | ✅ 已修复 | `MasterOverviewWorkspace.jsx:56-59` focus 仅置 stale 提示条；`refreshInPlace` 原地重读保留页码/选中/详情；数据变更事件仍回第 1 页（语义正确） |
| 12 | 跨页确认 | ✅ 已修复 | 「确认全部 N 道已核对」+ 二次确认弹窗（`ProcessHoursEditor.jsx:77-79`、`ProcessSourceEditor.jsx:108-110`）；保存报错按页汇总 +「定位到第 N 页」（`ProcessStageEditor.jsx:161-177`） |
| 13 | 假控件 | ✅ 已修复 | `PreflightControls.jsx:14` 改纯文本「已开工工序：保留记录（不可修改）」 |
| 14 | 候选甘特图例/语义冲突 | ✅ 已修复 | 候选图 critical 0 处（grep 实证），重叠改 overlap 色系+斜纹；色块图例三项；计划甘特 7 项图例保留——两图红色语义不再冲突 |
| 15 | 候选行动区 5 按钮并列 | ✅ 已修复 | rc-nav / rc-actions 分组 + 分隔线 +「试调不影响正式计划」标注；返回按钮降级为 `button.btn.link` 链接变体 |

## P2 复核汇总（40 条）

- **已修复 28 条**：L1（内嵌滚动位置按 `data-wb-scroll-key` 恢复，合同测试锁定）、L2（点名 4 处 z-index 清除）、L3（随 06 关闭）、L4（跳转标签与侧栏同名对齐）、L5（「下一步 · 去排产」三态）、L6（试调改 square-pen 图标 + 全局图标去重）、V1（阴影改 --ui-shadow-sm/md）、V3（选中改 primary 系）、V5（34px 全灭、新增 mini 令牌）、V7（甘特 face 结构：计划透明底+虚线、网格线去 opacity）、V10（monospace 统一）、V11（--leading-* 删除、--num-variant 被消费）、V12（停机窗去 opacity）、I2（收尾动词统一「完成」）、I3（采用补回退说明）、I4（值班台「去执行排产」）、I5（「候选方案待确认」解绑一词两用）、I6（统一「采用方案」）、I7（行话清扫 grep 0 命中）、I8（经办人本机记忆预填 WorkbenchHandlerMemory.js）、I9（长说明拆结论+折叠）、I10（Choice 搜索常驻+共用 Pager）、I11（工种 datalist 候选）、I12（筛选弹层只响应锚点祖先滚动）、I13（工艺空态四态对齐）、I14（图表刻度+空态）、I16（SelectMenu >8 项出过滤框、短列表键入回显）、I17→见下、I18（删除=勾选 / 恢复=勾选+手输两级模型）。
- **部分修复 3 条**：V4（点名 3 表已走密度令牌；范围外 4 表仍硬编码，见 R4）、V8（点名处已改实色；`34-run.css:33` 残留 opacity:.5，见 R3）、I1（TimelineZoom 共用组件已抽、三处迁移、aria 统一；缩放上限 1024/128/64 按绘制方式有意保留，现场实际甘特「自动/手动」模式未迁移）。
- **裁决有意不改 4 条**：L8（试调 URL 双轨，href 只产出 path 形式）、V2（warning 3px 边条 3.045:1 过阈值，转观察项 O4）、V9（字体单字重，Win7 中文版自带雅黑）、I15（分页档位由域接口申报是既定合同）。
- **复核撤销原判 3 条**：L7（≤900px 时 .nav-label 隐藏规则在 prototype 层 `operations-workspaces.css:8-13`，首轮只读 app 层误判）、L9（EmptyState 有正式 loading 档位带 role=status/aria-busy，非「空态顶替」）、I17（reasonDisplay 双模式是有意设计，注释+非法值抛错齐全）。
- **观察项 1 条**：L10（1920 宽屏留白/1280 拥挤为截图观察，布局属设计范畴）。
- **未复核 1 条**：V6（spacing 330 处/行高 22 处硬编码，本轮复核任务未列入；修复记录亦未点名，大概率维持原状——本来就是卫生项，建议随 prototype 退役专项处理）。

## 修复尾巴与新残留（12 条，均卫生级）

| # | 残留 | 位置 | 建议处置 |
|---|---|---|---|
| R1 | 步骤条短标签「检查」未写入 `ui_copy_glossary.json` allow 表（allow 现 15 条无此项） | `PreflightWorkspace.jsx:75` | 词表维护人确认后补一行，闭环 F10 |
| R2 | 3 处散文「无法评估」未收紧为「暂无数据」（「读不到或无法评估的来源」「无法评估 N 项」「资源压力无法评估」） | `DashboardPanels.jsx:52,63,89` | 词表裁决是否覆盖散文用法 |
| R3 | `.pf-segment input:disabled+span{opacity:.5}` 仍是透明度禁用 | `34-run.css:33` | 改实色禁用语言，与 20-controls 主语言对齐 |
| R4 | 4 张自绘表 padding 不响应密度开关 | `34-run.css:94`、`31-batches-resources.css:128`、`32-process-trial.css:61-62`、`33-gantt-foundation.css:44` | 改消费 `--wb-table-cell-*` |
| R5 | 4 处控件高度字面量残留（值与令牌档一致） | `36-analysis.css:119,122`、`34-run.css:30`、`32-calendar-outsourcing.css:73,87` | 走令牌，卫生项 |
| R6 | 阴影仍写死 `0 4px 16px var(--ui-border)` | `36-analysis.css:73` | 改 `--ui-shadow-md` |
| R7 | Choice 控件选项页 size 固定 50 且无档位切换（与 I15「域接口申报」裁决存在灰色地带，因该 50 是前端固定值） | `ResourceControls.jsx:239` | 拍板：接受现状或放开 onSize |
| R8 | 计划中心 4 个内嵌滚动区双层滚动（F07 方案 B 第二步） | `33-gantt-foundation.css:48,67,106,110` | 已立 issue `2026-09-14-wbui-double-scroll-1366`，等排期 |
| R9 | 排产记录态侧栏高亮与页头标题不一致（F06 尾巴） | `main.jsx:45` | 记录在案接受；如要做可按 context 加二级提示 |
| R10 | `theme.js` 源与 static 产物非逐字节（构建器重排版，语义已验证等价） | theme.js | 仅逐字节门禁需知悉，无风险 |
| R11 | 修复方自述观察：批次管理表 1280 宽下「优先级」列头被 sticky「操作」列遮半 | remediation-record 追加节 | 既有问题，建议另行核对立项 |
| R12 | opt-in 浏览器测试通道其余 8 项未跑（learning 已记录腐烂模式）；3 个无 pytest 入口探针既有失败 | `scripts/run_workbench_opt_in_browser.py` 覆盖范围 | 建议把 opt-in 通道纳入定期门禁 |

## 产物同步结论

- `frontend/workbench/app/styles` ↔ `static/workbench/app/styles`：17 文件逐字节一致；`prototype/tokens` 4 文件逐字节一致；`gantt-theme.css` 一致。
- JS/JSX：各修复标记在 static 产物中逐条命中（含 \uXXXX 转义形式比对）；产物 mtime 新于源文件，build_id 已刷新。
- 唯一例外：theme.js 产物为构建器重排版（去空白/括号），语义等价已验证，无交付风险。

## 复核方式与限制

4 个只读验证代理（视觉/布局/核心流程/辅助工作区）+ 主代理抽查（F02/F03/F09/F11 独立 grep 复核，结论一致）。本轮只读，未跑测试；修复方的定向验证（样式门禁 0 违规、文案扫描 0 命中、注册表合同 952 通过、浏览器探针 120+69 通过等）见其 remediation-record，本复核未重复执行，也未跑全量质量门禁。
