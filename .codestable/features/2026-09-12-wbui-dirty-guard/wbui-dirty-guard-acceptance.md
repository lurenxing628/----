---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-dirty-guard
status: "completed-with-validation-limit"
summary: "编辑器草稿保护、导航与历史恢复及原请求保留边界实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- frontend
- reliability
roadmap: workbench-ui-refinement
roadmap_item: wbui-dirty-guard
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 验收记录

## 实现范围

- `WorkbenchGuards.js` 管 owner 注册、草稿/已有命令锁定、单次确认、beforeunload 和一次性外部离开许可。`WorkbenchGuardHost.jsx` 独立依赖共享 Modal，portal 到 body；防止构建依赖成环、原弹窗遮挡确认框或确认框递归。
- Process 多阶段草稿、新增零件、文件导入、孤立待核实请求均接入全页保护；原有页内多阶段保留、文件丢弃确认及真实回执核对保持。工艺输入改回原值或仅切录入模式不误报草稿。
- Trial 工序调整、新建来源、场景名称及未提交的采用说明接入保护。工序切换只在用户确认后丢弃输入；已持久化的试调草稿不会误报。采用流程原有“关闭并保留请求”能力保留，不用界面守卫改写已保存的请求生命周期。
- 本域 5 处内嵌样式迁入 `styles/32-process-trial.css`，接字体与 z-index 令牌；工艺确认时间区分真正 UTC 时刻和遗留工厂本地文本；Trial 分页调用共享 Pager，原页码范围、大小限制、精确引用导航不变；本域表格补 caption/scope，内部引用折叠。

## 已完成验证

1. `.venv/bin/python -m pytest -q tests/workbench/test_dirty_guard_widgets.py -s`：通过。Chromium `109.0.5414.46`，11 个真实 React/Modal 行为场景，包含无改动、多 owner、同 owner 多注册独立注销、作用域、取消焦点、Esc、并发请求、pending 不可放弃、确认框免递归、beforeunload 及外部离开只确认一次。组件探针不访问业务数据库、不构建静态产物。
   - 证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-dirty-guard-81ycdr2o/dirty-guard-result.json`。
2. `.venv/bin/python -m pytest -q tests/workbench/test_process_detail_files.py tests/workbench/test_process_stage_commands.py tests/workbench/test_trial_predecessor_labels.py -s`：`118 passed in 72.27s`。其中工艺文件浏览器探针 52 个场景、28 张截图，errors/external 均为空。
   - 证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-process-detail-files-iqhe16q6/process-detail-files-result.json`。
3. `node tests/workbench-app-styles.cjs`：通过，包含本域 CSS，违规列表为空。本域样式 SHA-256：`5b65f829d7839e9dcc0f32c04fc02396a24b34984658d4e65bc037b538b9b833`。
4. 导航 owner 的整壳集成：build `02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4` 上，`test_ui_navigation_guard.py` 3 passed；真实 BatchForms 草稿后退拒绝、允许后离开 1 passed。拒绝时 URL、页面和输入保留。输入方法为真实 React 的 native setter/input event 与 DOM click，不冒充人工逐键验收；唯一非 GET 为只读 batch query。
   - 证据：`/tmp/aps-wbui-navigation-integration-20260912-round1/result.json`、`real-draft-result.json`。

## 快照行为通过但未绑定最终源

- ProcessStage：84 个行为场景、24 张截图全通过，errors/external 为空；随后 pytest 当前源码哈希核对因运行中 `WorkbenchFormat.js` 更新而失败。证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-process-stage-widgets-y9l9ydnr/process-stage-result.json`。
- ProcessWidgets：60 个行为场景、24 张截图全通过，随后同样因共享格式化模块变化而拒绝当前源码绑定。证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-process-widgets-t37e20tw/process-result.json`。
- Trial full：4 个尺寸/主题组合、86 个检查、29 张截图，真实 Flask/SQLite 保存、丢回包恢复、导出字段与原数量证明通过；运行中 CSS 清单新增文件，最终清单绑定拒绝。证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-cn-trial-widgets-a_uurxv2/`。

这些结果不能代替最终版本验收。三个原测试保留当前源码哈希检查，没有放宽、跳过或吞掉失败；最终全局冻结后重跑。统一构建、整站几何、daily/quality gate 及最终 build_id 由主线程集成记录。本工作区存在预先已有的调度优化改动，本记录不声明 clean-worktree proof。


## 主线程最终构建补验

最终补验：在UI-only隔离副本执行 `test_process_widgets.py test_process_stage_widgets.py test_trial_widgets.py`，**5 passed in 422.64s**。副本包含最终54c40205构建与相同UI源，Process/Stage/Trial的真实交互、导出/业务事实及结束时源码/CSS哈希检查全部通过，关闭此前仅旧快照通过但源绑定失败的待项。结果见 `evidence/workbench-ui/2026-09-12-final/process-trial-final.log` 与 `domains/`。
