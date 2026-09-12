---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-header-controls
status: "completed-with-validation-limit"
date: &id001 2026-09-12
roadmap: workbench-ui-refinement
roadmap_item: wbui-header-controls
summary: "顶栏主题、帮助、密度、实例标签及子页标题实现已收尾；验收结论为completed-with-validation-limit。"
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

已接入实例标签、帮助、切换深色/浅色动作、全局紧凑表格偏好及错误提示。帮助经`WorkbenchGuards.leaveExternal`单次确认；排产历史标题由明确context生成。main原服务器消息样式迁入11-navigation.css，语义颜色和文字徽标同时呈现。

验证：main.jsx用现有scripts/workbench/compile.cjs独立编译返回0；导航浏览器合同覆盖排产历史与候选上下文标题；只读手册路由合同通过。尚未在完整最终构建验证顶栏实际点击、双尺寸主题几何和退出弹窗，本文件不宣称界面终验完成。

本条影响全部工作区顶栏及旧浏览器验收中的主题按钮名称；主线程统一更新相关选择器并在新build_id下重跑。密度模块由主线程提供；共享草稿守卫由对应owner提供。未修改领域API，未做Win7发布。

首轮集成补充：主线程构建`02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`下，顶栏真实浏览器用例已验证实例文本、帮助地址、主题切换动作名称变化、密度切换和aria-pressed/data-density一致，完整导航文件29 passed。已目视1392宽暗色顶栏截图，无控件重叠。源与manifest前后不变，证据聚合见`/tmp/aps-wbui-navigation-integration-20260912-round1/result.json`；顶栏截图为`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-A-web-contract-1scj94t0/page.png`。最终双尺寸几何及最终build仍待统一验收。
