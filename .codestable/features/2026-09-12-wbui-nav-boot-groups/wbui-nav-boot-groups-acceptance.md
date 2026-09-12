---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-nav-boot-groups
status: "completed-with-validation-limit"
date: &id001 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-nav-boot-groups
summary: "启动信息驱动的导航分组、视图别名及原URL和上下文合同实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- ui
created: *id001
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

已实现导航呈现元数据、12项菜单、15个支持视图和3个别名；生产壳不再消费原型NAV_GROUPS。`help_url`复用既有手册路由。独立支持集合与菜单产品清单继续锁定，不用生产返回推导全部期望。

局部验证：`pytest tests/web_pages/test_workbench_nav_entry_contract.py -q -k 'not renders_approved and not default_ui and not is_readonly and not preserves_report'` 为23 passed、4 deselected；`pytest tests/workbench/test_ui_navigation_guard.py -q` 为2 passed，其中元数据7类非法输入均拒绝。真实Chromium109运行的是当前源JS与隔离空页，不能写成完整工作台验证。

受影响所有工作区菜单与对应旧URL。完整菜单DOM、整壳加载、双尺寸双主题和最终源码/build_id由主线程统一构建后补充；未运行主目录构建或提交。当前工作区包含原有调度优化改动，不是clean-worktree proof。

首轮集成补充：在主线程构建`02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`上，完整`test_workbench_nav_entry_contract.py`29项通过；元数据/源JS历史测试3项通过。9份真实Chromium109浏览器结果无pageerror和外部请求。导航产品、测试源前后无变化，3个前端输入与构建哈希相同，manifest前后不变。聚合证据与源绑定：`/tmp/aps-wbui-navigation-integration-20260912-round1/result.json`和`sources-before.json`。这是集成反馈轮，最终统一构建及双尺寸几何仍待主线程补齐。
