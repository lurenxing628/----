---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-plan-center-first-screen
status: "completed-with-validation-limit"
summary: "计划中心的来源选择、目录折叠、首屏甘特及任务恢复实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- ui
- gantt
roadmap: workbench-ui-refinement
roadmap_item: wbui-plan-center-first-screen
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

## 1. 接口契约核对

无 Python 领域/API 改动。PlanSelectionModel 只在无显式引用、无恢复上下文时选唯一可读当前正式；PlanCatalogUI 仍请求 size=20 的游标目录并携带 snapshot_ref，未虚构总页数。PlanWorkspace 使用响应 meta.as_of，未以客户端当前时间覆盖。统一消费 WorkbenchFormat、EmptyState、Pager 与表格框；三入口切换由真实 main 页签负责。

## 2. 行为与决策核对

目录选中后折叠，顶部下拉可切换，键盘从目录选中后焦点回到展开按钮。条形 DOM/canvas 首行均显示批次号，次行保留工序及分件。图例覆盖准时、超期、冲突、初始基线、零时长点。今日零点及数据时点均来自服务器 as_of，仅在轴范围内绘制。风险/冲突表移至甘特之后，范围说明仍完整保留。

根集成检查发现独立组件测试缺少真实壳的页签/排产记录栏预算，原“露出若干像素”不可算 G3 通过；随后压缩已选后的重复 h2、目录和读取工具间距、概览高度、范围说明边距，指标卡由共享覆盖层从旧 78px 改为56px。保留名称、身份、范围文字及所有操作。

## 3. 验收场景核对

- `tests/workbench/test_wbui_plan_gantt_models.py`：唯一可读当前、显式计划、查询/任务/快照恢复、不可读、多当前、空目录等合同通过。
- `tests/workbench/test_plan_ui.py`：Chrome 109.0.5414.46，51 场景、509 断言、31 张截图通过；包含导出、取消、陈旧读取、未知证据、10000 道安排虚拟化、键盘和主题。证据：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-plan-ui-dvktoe3p/plan-ui-result.json`。这次通过早于后续整壳预算收紧，不冒充最终样式证据。
- `test_wbui_plan_first_screen.py`：独立组件两尺寸×三视图、显式失败不回退、上下午数据时点与顶部下拉通过；仅作为组件证据。
- `test_fg_plan_workspace_actions.py` 已扩充真实 main 的1280×720、1366×768，必须第一完整任务行和条形 bottom≤viewport；最终结果待追加。
- 三处运行时 style 已迁到33-gantt-foundation.css，CSS 全量扫描17文件0违规，最终字体token变化后重测。

## 4. 术语一致性

风险详情使用 WorkbenchTerms.delay_hours；只读取已验证的业务标签，内部引用没有新增可见裸露。大整数数量文本保持原样，不先转 Number。

## 5. 架构归并

新增 PlanSelectionModel 与两份33 CSS是前端显示层；不改计划选择、排产和报工业务规则。工作台共享结构由主线程统一归并。

## 6. Requirement 回写

原有计划读取和甘特能力范围未改变；本项是界面质量改进，未创建新的领域需求。

## 7. Roadmap 回写

主线程独占路线图清单；本项保持实施中，最终统一构建、真实整壳 G3 与门禁完成后回写，不能用独立组件通过提前标 done。

## 8. Attention 候选盘点

本轮无需要永久写入项目注意事项的新业务规则。独立组件原型 AppShell 与 production main 的导航/主题入口不同，测试分别使用真实宿主，不批量猜替。

## 9. 遗留

工作区已有他人调度优化改动。本项不暂存、不提交；所有通过均为 dirty 工作区局部证明。最终 source/build_id、统一几何与质量门禁由主线程绑定；Win7 硬件/发布仍属于迁移路线图。
