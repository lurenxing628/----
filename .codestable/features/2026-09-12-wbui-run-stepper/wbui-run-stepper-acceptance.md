---
doc_type: feature-acceptance
slug: wbui-run-stepper
status: "completed-with-validation-limit"
created: 2026-09-12
feature: 2026-09-12-wbui-run-stepper
roadmap: workbench-ui-refinement
roadmap_item: wbui-run-stepper
summary: "排产步骤、主操作、耗时及参数变化后重检提示实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- ui
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 排产业域实施与验收交接

本项产品实现完成；最终构建、目标尺寸整壳几何和共享源码冻结后的浏览器绑定由主线程统一收口。没有将分支分配、旧截图或前端局部测试记为 roadmap 完成。

本域收尾源码及 HEAD 哈希见 `evidence/run-ui-source.json`，明确 `build_id: null`、`clean_worktree_proof: false`，等待统一发布构建后回填关联证据。

## 实现范围

- `RunPresentation.js` 与 `PreflightWorkspace.jsx`：三步条、跟随步骤的主操作、参数变更立即清预检结果并提示重新检查；不会清除运行 `pending` 或更换原请求键。
- `PreflightBatchPicker.jsx`：交期与优先级、共享 Pager/空态。非法交期是领域 DTO 允许保留的原值：显示“交期原值待核对”，折叠保留原文和格式原因，不让整页抛异常。
- `RunJobControls.jsx` / `RunJobPanel.jsx` / `SchedulingWorkspace.jsx`：中文计算阶段和已耗时、空范围不重复突出主操作、只读运行编号折叠。运行预览、确认、未知结果查询、受理和恢复逻辑未改。
- `RunCandidate*` / `RunBaseline*` / `RunAdoption*`：采用方案为唯一主操作；与壳页签重复的甘特/风险导航已移除。合法大整数经 `integerText` 精确呈现，百分比不通过 `Number` 丢精度；UTC 回执与工厂本地时间分别处理。编号保留于 `details.wb-ref`，Canvas 标题和无障碍名称使用业务描述。
- `RunHistory*`：保留 10/20/50 领域档位、共享空态和分页、使用内部表格高度预算。候选目录与批次各自保留已有分页合同。
- `styles/34-run.css`：迁出 8 处内嵌样式；字色、字号、层级和圆角使用令牌；原生表格 caption/scope、关键列和操作列粘滞、候选虚拟表的 columnheader/row/cell/rowindex 语义与水平对齐。
- `tests/workbench/run_ui_source.cjs`：已有本域源码浏览器测试明确加载完整共享依赖，直接载入并保存当前 CSS 源码与哈希；未通过静默 stub 或旧发布 CSS 绕开新合同。

## 已完成验证

1. `node tests/workbench/test_run_ui_refinement.cjs` 在 `Asia/Shanghai`、`America/New_York`、`UTC` 三时区通过：空范围/已选择/检查后的步骤、已结束与运行中的耗时、异常时间不伪造耗时、超大整数及百分比精度。
2. 26 个 `Preflight*` / `Run*` / `SchedulingWorkspace.jsx` 源文件通过 Babel Chrome109 编译；本域 `git diff --check` 和 CodeStable YAML 校验通过。
3. 一次完整命令 `pytest test_preflight_browser.py test_run_adoption_widgets.py test_run_history_widgets.py` 返回 **3 passed in 170.56s**。三套均通过各自 4 个 Chrome109 尺寸/主题组合及当次源码哈希绑定。预检验证只读数据不变；采用验证原数据与类型保留、真实采用回执、未知结果不重复提交；历史验证读 HTTP/SQL、原始来源和接口隔离。
4. 上述采用证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-run-adoption-widgets-6i67e1f2/`，64 项动作、24 张截图。历史证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-run-history-widgets-_5_29srm/`，264 项动作、52 张截图。
5. 加入非法交期用例后的预检 4 组合全部浏览器动作通过，证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-preflight-browser-174a96aw/`，32 张截图；当次 pytest 最后被正在并行更新的共享 `WorkbenchListControls.jsx` / `22-shared-controls.css` 哈希漂移阻断。不能将这轮写成最终源码绑定通过。
6. 候选旧实施快照完成 4 组合、228 项动作、24 份真实 CSV/XLSX 下载核对与 5000 工序容量；运行旧实施快照完成 4 组合、245 项动作、5000 工序/20000 候选任务，业务事实不变。证据分别为 `aps-run-candidate-widgets-bsisrk3l/` 和 `aps-run-job-widgets-6usd4pcj/`（位于上述临时目录根）。两次 pytest 都被后续本域 CSS 更新的源码哈希漂移阻断，属于旧实施快照证据，不作为最终完成凭据。
7. 最新候选复验 `aps-run-candidate-widgets-i6nt9tzi/` 完成 4 组合、232 项动作、24 份下载及 5000 工序容量，`errors=[]`。新增虚拟表 5 个 columnheader、row/column 数、业务无障碍名称、Canvas End/Home/ArrowRight 均已跑到；最终源码比较仅因本次测试过程中 `RunCandidateControls.jsx` 固定列和术语收尾变化拒绝绑定。最终产品源码现已冻结，仍须统一再绑一次。
8. `test_run_baseline_widgets.py` 已通过（与上条候选合跑结果 `1 failed, 1 passed in 432.38s`，失败仅为候选旧源码哈希）。基线证据 `aps-run-baseline-widgets-t7j4wdh3/` 通过其 Chrome109 矩阵、真实基线/候选对照和当次源码绑定；没有修改或放宽基线业务断言。
9. **最终本域候选源码绑定通过**：`test_run_candidate_widgets.py` 返回 **1 passed in 214.73s**。证据 `aps-run-candidate-widgets-11v_vibm/`：Chrome109 4 组合、232 项动作、24 份 CSV/XLSX 导出、12 次 5000 工序容量观测，`errors=[]`，全部源码/CSS 哈希及 SQLite 只读保留证明通过。该轮绑定的是固定列和无名称候选描述修正后的最终源码。

## 复核与剩余事项

- 独立只读复核确认的两项 P2（非法交期原值与大整数字符串）已按领域真实合同修复；没有修改 DTO、后端计算或采用事务。
- 并行后端优化期间，候选/基线测试曾在收集时报 `native_multi_start_calendar_snapshot` 导入失败；随后重试导入恢复。另一次运行容量等待 `complete` 超过 300 秒，未弱化该断言，也未修改其他人的后端代码。
- 本域依赖共享样式/控件和 PointGantt。候选与基线本域最终源码绑定已通过；若共享文件后续变化，统一构建后重跑受影响证据。`test_run_job_widgets.py` 最后容量超时仍需在稳定后端上重跑；整壳 `test_run_presentation.py` 需使用最终导航 boot 与构建。
- 主线程确认 `build-order.json` 已登记 `RunPresentation.js`（早于 PreflightWorkspace/RunJobControls）和 `styles/34-run.css`。最终 static/build_id、1280×720 / 1366×768 整壳几何、完整 gate 和 Win7 证据不在本分支伪记完成。
- 无 git add、commit、push；未更改后端 Python，原有调度优化暂存与未暂存文件均保留。


## 主线程最终构建补验

最终容量补验：在UI-only稳定后端副本运行 `test_run_job_widgets.py` 已通过；5000工序、4候选/20000候选任务，真实计算、四尺寸主题组合、业务事实保留与源码哈希均通过。原容量300秒超时待项关闭。合跑的整壳presentation测试因旧boot夹具缺少新导航字段未能进页；仅更新该测试夹具后正在复跑，未修改产品合同。原完整命令记录见 `evidence/workbench-ui/2026-09-12-final/run-final.log`，通过的容量JSON与SQLite证明见 `domains/aps-run-job-widgets-8enijucn/`。

后续局部结果补记：上述 presentation 入口已有实际通过日志 `evidence/workbench-ui/2026-09-12-final/presentation-final-v6.log`，为 **1 passed in 356.34s**；原始结果为同证据根目录 `run-presentation/presentation.json`。该 JSON 明确 `compile.global_build:false`，因此这里只关闭“当次入口仍在复跑”的状态，不把它升级为最终统一构建或整仓门禁通过。
