---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-terms-and-ids
status: "completed-with-validation-limit"
summary: "统一术语、内部编号与技术诊断折叠及原值保留实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- terminology
- ui
roadmap: workbench-ui-refinement
roadmap_item: wbui-terms-and-ids
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 术语与编号验收记录

- 新增冻结 `WorkbenchTerms`、`WorkbenchReference` 和 `WorkbenchError`。编号组件默认收起，完整原值保留为 React 文本；业务消息可见，技术诊断折叠，字段错误按路径排除并去重。
- `node tests/workbench-terms-and-ids.cjs` 通过。测试使用本地 Babel 编译实际 JSX，并检查独立 React 元素树：长引用在 details 内、空引用不生成空框、HTML 作为文本、技术错误完整保留、普通中文业务消息不丢失、不修改原错误、重复/排除字段只显示一次。
- 测试没有实际浏览器布局证据；本线程 Node 默认解析路径没有 playwright，统一 G6/键盘展开和布局由整轮浏览器任务执行。直接加载源码，无独立 build_id。

## 消费者迁移说明

`<code>{row.run_ref}</code>` 换为 `<window.WorkbenchReference entries={{'运行编号': row.run_ref}} />`。组合引用使用对象映射；业务批次号和正常计划显示名称保留可见，不以单纯同名字段强行归一。

各域错误框可委托 `WorkbenchError({error,fallback,fields,excludePaths,hideMessage})`。`fields` 为 `[{path,message,code?}]`；已由 Field 渲染的路径通过 excludePaths 排除。若总消息与已呈现字段错误完全相同，hideMessage=true 仅隐藏重复总消息，其他字段与内部诊断继续保留。不传 fields 时组件不自动读取 error.fields，防止重复显示。

默认词表与编号组件接口已广播所有工作区 owner。ResourceControls 集成由 shared_controls 负责，公共样式由 style_foundation 负责，构建顺序由主线程登记在消费者前。

## 尚待整轮收口

- 各工作区内部编号、错误码与同义文案的实际迁移和 G6 回归。
- 统一 build_id、截图与主线程总门禁；完成前 consumers-g6 保持 pending。
- 工作区已有其他未提交修改，本项未暂存、未提交，不构成 clean-worktree proof。
