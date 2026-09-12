---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-actual-gantt-window
status: "completed-with-validation-limit"
summary: "现场实际甘特的显示窗口、缩放恢复与点工序交互实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- ui
- actual-gantt
roadmap: workbench-ui-refinement
roadmap_item: wbui-actual-gantt-window
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

未改 Python 或 DTO。axis_span 仍为原后端并集，点标记留白仍由 PointGanttModel.bounds 处理；as_of、点工序、未填报工结束、数量/工时及导出原样。ActualGanttWindow 只计算显示 zoom/center 和命中几何。

## 2. 行为与决策核对

首次显示优先对齐计划区间，无计划端点时使用实际报工范围；恢复 actual_view 优先。缩放以所选报工、所选计划任务或数据中心为锚；适应全部回到完整显示轴。

正常条形的透明命中框最小4px，着色面维持真实时长宽度；靠近轴边界仍保留4px点击区。同一行短条命中重叠时，DOM 和 canvas 都选距离真实时段中心最近的条目；点保持24px菱形和零持续时长。

复审修正了 apply 范围切换时序：同步清空旧 result，再让新响应初始化窗口，避免 useLayoutEffect 提前消费旧范围。DenseRow 支持方向键、Home/End 遍历全部 marks，Enter/Space 激活当前色块并滚动定位，含第二条和最后报工；空行不可聚焦。

## 3. 验收场景核对

- `test_actual_gantt_ui.py` 模型与实际 Chrome109通过，工厂本地跨DST坐标不变，源DTO未修改。
- 最新 browser 证据 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/actual-gantt-ui-bmxop0bq/result.json`：30次真实fixture API读取、10000任务仅8虚拟行、canvas真实像素边界、11截图、外部请求/页面错误为空，数据库前后相同。
- 1秒报工命中框4px，真实着色宽约0.024px；4px区内可点击、未扩大工时。适应全部后 scrollLeft=0且scrollWidth=clientWidth。
- 范围A8小时→B1小时：新响应轴画布从8295.5px变为66364.1px，B条形位于可见区，说明初始化使用B。
- `test_wbui_actual_keyboard.py`：Chrome109逐一激活65 marks，包含报工2、点4、末条64、计划/剩余，水平滚动超过10000px，Tab退出和DTO不变。证据 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-wbui-actual-keyboard-289qehp0/result.json`。
- 本轮上述回归连同独立计划首屏4项pytest通过，20.03s。最终统一字体token/构建后的证据由主线程追加。

## 4. 术语一致性

工厂时间由 WorkbenchFormat.dateTime 显示；未知值不显示0。实际色块、计划基线和剩余安排仍沿用原领域名称，不把显示窗口写成查询范围。

## 5. 架构归并

仅新增前端显示计算 helper；三个运行时 style 已集中33-gantt-foundation.css，局部隔离画布保留原层级关系。共享前端文档由主线程统一归并。

## 6. Requirement 回写

未改变实际记录/计划对照能力，故不创建领域需求。键盘访问补齐现有色块的可操作性。

## 7. Roadmap 回写

主线程独占状态；等待最终source/build_id、统一浏览器与门禁后回写。

## 8. Attention 候选盘点

范围切换必须先清旧显示数据再初始化新视窗，此处已有A→B回归锁住，不额外修改长期规则。

## 9. 遗留

无已知未修复本项合同偏差；现有证明均属于dirty工作区局部验证。单独启动的Point downstream真实main与FA/FG回归仍在对新导航/样式合同适配验证；Win7发布验收不在此项替代。


## 主线程最终构建补验

最终恢复修正与验证：视窗位置新增可见时间中心和可见时长，刷新后axis_span/as_of变化与跨宽度恢复按时间还原；旧记录保留原显式像素/zoom兼容路径，新范围仍按计划初始化。模型合同覆盖时间轴两端变化、1400→810视口、缩放上限和DTO不变；实际甘特两项及65色块完整键盘测试通过，真实main+Flask/SQLite点工序测试 **2 passed in 24.88s**，含1920→1392、重载、刷新、报工点、跨页返回及导出。最终浏览器build_id为54c40205c9063d08147de7ff516d3bfe0430f314ab336712b37c4060f1e491f5。详见 `evidence/workbench-ui/2026-09-12-final/actual-window/`、`actual-keyboard/` 与 `actual-final-point.log`。
