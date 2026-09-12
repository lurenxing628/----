---
doc_type: issue-fix
status: fixed
created: 2026-09-13
summary: 工作台 UI 整改复审后定点修复 7 项：格式精度退化与报工丢秒、守卫 locked 混入 UI 忙碌态、页签切换丢范围（后证实为既有设计，已回退）、帮助丢上下文、报工保存提示常驻、值班台业务字段被折叠、排产历史下页签条矛盾
tags: [workbench, ui, format, guards, navigation, regression]
---

# 背景与边界

- 来源：2026-09-13 对 `workbench-ui-refinement` 21 项实现做五路只读复审（外壳导航 / 共享控件 / 样式与原型清理 / 工作区回归 / 验收证据），主代理逐条用源码或真机复核后确认 7 项必修。复审中被推翻的结论（1280 宽顶栏胶囊隐藏）不在此列。
- 只改 `frontend/workbench/app/` 消费层与共享模块、对应测试和路线图 / 架构文档；不改领域 API、DTO、业务规则、原型层快照，不改排产优化器改动。
- 工作区同时含他人未提交的排产优化器改动（`core/`、`tests/algorithm/` 等），本轮未触碰、未 `git add`、未提交。**没有跑完整门禁，不是 clean-worktree proof**；实跑范围见下文"验证"。

# 根因与改法

1. **格式精度退化与报工丢秒**。`WorkbenchFormat.hours/number` 默认 1 位固定小数，被直接用于写入确认对照表、报工累计工时、候选对比指标，原实现分别是精确原值 / 3 位 / 3 位；`FieldContract.date` 改用 `dateTime` 时漏传 `seconds`，而报工时间是秒级事实。
   - `WorkbenchFormat.js`：`number/percent/hours` 统一接受 `digits | { digits, trim }`；`trim=true` 去掉末尾 0（"最多 digits 位"），`-0` 与四舍五入到 0 的值显示为 0；三个函数共用一处选项校验，`hours` 的非法输入报"工时"而非"数值"。
   - `BatchForms.jsx` / `BatchDetail.jsx`：换型、单件工时用 `{ digits: 4, trim: true }`，外协周期天数 `{ digits: 1, trim: true }`，确认对照表按录入值显示。
   - `FieldFilters.jsx`、`FieldEditorFields.jsx`：累计实报工时、已知小计、作业跨度、工时差额 `{ digits: 3, trim: true }`（与原 `Math.round(x*1000)/1000` 一致）。
   - `RunCandidateModel.js`：对比指标 `{ digits: 3, trim: true }`（与原 `maximumFractionDigits: 3` 一致）。
   - `FieldContract.js`：`date` 传 `{ seconds: true }`，逐次报工、时间线、录入时间保留秒。
2. **守卫 locked 混入 UI 忙碌态**。`ResourceForms.jsx` 把子目录弹窗打开、重读资料两种 UI 状态也传成 `locked`，侧栏导航时弹"原请求尚未核实"且无放弃按钮。改为 `locked: command.locked`；关闭表单时对忙碌态的早退保留。
   - 顺带修 `WorkbenchGuards.js`：确认框等待期间受保护条目全部保存或卸载时自动 `resolve(true)` 并关闭空确认框（原来留下无内容的对话框且导航挂起）。
3. **报表 / 复盘页签切换丢范围（已回退）**。复审时把 `WorkbenchNavigation.navigate` 在 `preferSaved` 命中缓存的分支改成 `{ ...saved.context, ...supplied }`，想让当前 scope / topic 跟着页签走。同日 `tests/workbench` 全目录长跑证明这是误判：HEAD（`go()` 的 returnTo 捷径）与整改版（`preferSaved`）都是整体恢复目标页签自己的上下文，验收用例 WBP-SCOPE-005 / WBP-REPORT-010 锁定重进页签必须恢复它自己的 query、分页、选中；叠加语义还会把复盘的 topic 压到报表保存的 table 上，页面报"报表专题、排序或分页无效"且不再发请求。已回退为整体恢复，`test_ui_navigation_guard.py` 的合同同步改回；`helpUrl`、`historyView` 不受影响。
4. **帮助入口丢上下文**。`help_url` 不带 `src`，手册页不渲染返回链接。新增 `WorkbenchNavigation.helpUrl(boot, page)` 附加 `src=当前视图 URL`，顶栏链接与 `openHelp` 都走它；手册页据此渲染"返回刚才页面"。boot 字段本身不变。
5. **报工保存提示常驻**。`FieldWorkspace.jsx` 的 `notice` 只在保存后赋值、从不清空，之后任何读取失败都显示"报工已保存，但重读失败"。筛选、刷新、翻页、改每页数量时清空提示；保存后的自动重读仍按原逻辑显示结果。
6. **值班台业务字段被折叠**。`DashboardEvidence.jsx` 的引用判定正则把 `business_code`、`kind` 当技术引用收进编号折叠区。改为与 `ReportEvidence` 同一语义：只折叠诊断码（`code/rule/rule_code/diagnostic_code/request_key`）、`*_ref/*_refs/*_key/*_snapshot` 与非业务字段中的完整 32 位以上十六进制。
7. **排产历史下页签条自相矛盾**。壳层只按 `view` 决定是否渲染计划中心页签条，进入排产历史后页签高亮"选择排产方案"、页头写"排产历史"、切页签内容不变。新增 `WorkbenchNavigation.historyView(page)`（与 `title()` 共用判定），`main.jsx` 在历史上下文中不渲染页签条与 tabpanel 角色。

# 改动文件

- 产品：`frontend/workbench/app/{WorkbenchFormat.js, WorkbenchGuards.js, WorkbenchNavigation.js, main.jsx, ResourceForms.jsx, FieldWorkspace.jsx, FieldContract.js, FieldFilters.jsx, FieldEditorFields.jsx, BatchForms.jsx, BatchDetail.jsx, RunCandidateModel.js, DashboardEvidence.jsx}`；`static/workbench/` 由 `scripts/workbench/build.py` 重新生成（build_id `e709825b…239b5`）。
- 测试：`tests/workbench-format.cjs`（trim / -0 / 选项校验）、新增 `tests/workbench-guards.cjs`（locked 语义、空确认框自动关闭、监听器不泄漏）并登记进 `tests/workbench/test_ui_refinement_node_contracts.py`；`tests/workbench/test_ui_navigation_guard.py`（页签整体恢复语义、`historyView`、`helpUrl`）；`tests/web_pages/test_workbench_nav_entry_contract.py`（帮助链接带 src、手册返回链接、壳层源码合同）；`tests/workbench/analysis_ui_contract.cjs`（业务编号可见、请求键与规则码折叠）；`tests/workbench/batch_widgets_probe.cjs`（单件 0 h 期望）；`tests/workbench/field_fastpath_browser.cjs`（手动刷新清除保存提示）。
- 文档：路线图 4.4 / 4.5 合同文本与变更日志、`architecture/workbench-shell.md` 现状；items.yaml 与主文档 21 条重复的收尾段落改为一句指向验收记录。

# 验证

| 范围 | 结果 |
| --- | --- |
| `node tests/workbench-format.cjs`、`workbench-guards.cjs`、`workbench/analysis_ui_contract.cjs`、`workbench/test_field_fastpath.cjs`、`workbench/test_run_ui_refinement.cjs`、`workbench/test_wbui_plan_gantt_models.cjs` | 全部通过 |
| 重新构建后 21 个 pytest 模块（入口 / 清单 / 样式 / 构建源、导航合同、导航守卫、草稿守卫、共享控件、批次组件、值班台细化、报表导航、手册登记等，含真实 Chromium 109） | 201 passed / 1 skipped |
| `tests/web_pages/test_workbench_nav_entry_contract.py` 单独重跑 | 30 passed |
| `tests/gate_meta/test_workbench_registry_contract.py`、`test_workbench_round1_registry_contract.py`、`test_long_gate_manifest.py` | 通过（新增 cjs 落在既有 `tests/workbench-*.cjs` 输入范围内，无需改登记） |
| `NODE_PATH=… WORKBENCH_BROWSER=… node tests/workbench/field_fastpath_browser.cjs <仓库外输出目录>`（真实 Flask+SQLite 后端 + Chromium 109.0.5414.46） | 7 个用例全部通过，含新增的"手动刷新清除保存提示"断言；pageerror 为空 |
| 同日 `tests/workbench` 全目录长跑（含第二轮样式改动） | 9 failed / 8376 passed；分析页签、复盘重进、报表明细 3 例由第 3 项引起，回退后 8 例真机用例复跑通过；第 1 项对应的 3 处测试期望改回 HEAD 语义。归因全文见 `../../features/2026-09-13-wbui-style-round2/wbui-style-round2-implementation.md` 补记 |
| 未跑 | 完整门禁、daily gate、e696 浏览器矩阵；`tests/workbench/field_workspace_probe.cjs` 因期望的按钮名早已与产品不一致（缺 `· 共同工序` 后缀）无法运行，属既有陈旧探针，未修 |

# 遗留

- 复审里未处理的中低优先级项仍在主代理报告中：共享控件 CSS 混入业务规则与 `!important` 压死工作区表格声明、override 注释模板化、7 处表格框夹层、严重度令牌暗色不适配、维护恢复页折叠区缺 `wb-ref`、首屏读取失败不注册 popstate、`confirmLeave` 无宿主时 reject 无人接、-0 以外的 `percent` 位置参数写法不一致（已兼容对象写法）。
- 几何门禁仍是 daily gate 显式选项；`evidence/` 目录被 .gitignore 忽略；工作区 UI 与优化器改动仍需分开提交。
