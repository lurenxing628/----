---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-view-tabs-merge
status: "completed-with-validation-limit"
date: &id001 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-view-tabs-merge
summary: "计划与报表页签整合、旧视图可达性及草稿和历史上下文实现已收尾；验收结论为completed-with-validation-limit。"
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

计划三页签由壳呈现，沿当前view与精确history context导航。报表/复盘页签由报表owner在既有go协议中集成，不在壳猜测scope/returnTo。菜单别名只负责高亮，旧gantt/review/delay URL及nav.view不重写。

`tests/workbench/test_ui_navigation_guard.py`真实Chromium109源JS合同通过：两步后退时先恢复原URL再确认，拒绝后原草稿与上下文保持；随后后退允许、前进拒绝、干净状态前进均正常。此测试使用隔离空页验证实际浏览器历史，不替代真实表单/完整React壳验收。原`node tests/workbench/final_foundation_navigation.cjs`25项通过。

待主线程统一build后验证真实计划页签、报表页签、浏览器重载和完整草稿弹窗；源码/build_id绑定待补。共享导航变化影响全站返回路径，旧B/K/V/P证据不得自动重记为新版本通过。本条未提交，不是clean-worktree proof。

首轮集成补充：构建`02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`上，完整壳测试实测gantt显式计划/日期范围进页后切delay，原context和alias高亮保持，指定不存在计划明确报错而不替换其它计划。另新增真实浏览器重复3轮go(-2)/go(2)，覆盖初始显式nav返回key=0及确认中再次后退，6次确认/6次恢复通过。源JS测试3 passed、完整导航29 passed、原Node历史合同加初始化坏缓存回归26/26。证据及source/build绑定见`/tmp/aps-wbui-navigation-integration-20260912-round1/result.json`。最终报表页签和真实草稿整壳交互仍随主线程最终证据收口。

真实表单桥接补证：同首轮构建新增测试从值班台实际打开批次管理与新增批次，使用DOM点击及原生input setter/input事件经过React写入未保存草稿；浏览器后退拒绝后原URL、编辑器和输入值均保持，后退确认后回值班台且脏owner注销。`1 passed,29 deselected`；此为真实浏览器自动化，非人工逐键证据。结果及请求方法审计见`/tmp/aps-wbui-navigation-integration-20260912-round1/real-draft-result.json`，唯一非GET请求为批次列表`POST /api/workbench/v1/entities/batch/query`，没有提交批次创建或其它业务命令。新增测试后完整导航文件共30项，最终统一构建上需全文件重跑。

集成发现：给现有计划页签测试加入Alt+Left断言后，首轮构建真实失败`Tabs swallowed the browser back shortcut`，产物`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-A-web-contract-myde8yca`。已在main页签键盘处理放行alt/ctrl/meta修饰键；普通箭头仅移动焦点的断言同时锁住。修复待主线程下一次构建后验证，此处不把源码修改冒充通过。


## 主线程最终构建补验

最终导航补验：`test_workbench_nav_entry_contract.py`全文件与历史合同/证据测试合计 **56 passed in 70.76s**，绑定最终54c40205静态构建。其中页签测试验证Alt+Left不被阻止、普通箭头只移动焦点、显式计划/日期范围与alias保留；真实BatchForms草稿后退拒绝/允许也通过。此前“修复待构建验证”已由本轮结果关闭。
