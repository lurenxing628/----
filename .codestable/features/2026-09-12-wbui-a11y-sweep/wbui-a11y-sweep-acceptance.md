---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-a11y-sweep
roadmap: workbench-ui-refinement
roadmap_item: wbui-a11y-sweep
status: "completed-with-validation-limit"
summary: "表格语义、可见禁用原因及键盘与焦点交互实现已收尾；验收结论为completed-with-validation-limit。"
tags: [workbench, ui, accessibility]
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 无障碍验收证据索引

## 最终构建与矩阵观测

本文件仅整理已存在的证据，没有重跑测试或修改产品。最终矩阵为 [final54-ui/report.json](/tmp/aps-wbui-implementation-20260912/final54-ui/report.json)，浏览器 `109.0.5414.46`，构建 `54c40205c9063d08147de7ff516d3bfe0430f314ab336712b37c4060f1e491f5`。报告中的 manifest SHA-256 为 `cbe7910391fc97ef2969e27770bd51d1148fbbe579c803d1760fcb46cea21c39`，与其冻结目录内的 manifest 实际字节一致。

矩阵包含 15 个视图 × 1366×768/1280×720 × 浅/深色，共 60 个页面状态，以及 8 个真实点击/检查/滚动交互状态。报告总 errors、各页面 errors、各交互 errors 均为空。下表计数是重复状态中的观测次数，不是不同表格或不同按钮的数量。

| 观测 | 60 个页面状态 | 8 个交互状态 | 合计 |
| --- | ---: | ---: | ---: |
| 有表格观测的状态 | 52 | 7 | 59 |
| 表格观测次数 | 72 | 8 | 80 |
| caption 缺项 | 0 | 0 | 0 |
| 表头 missingScope 非空 | 0 | 0 | 0 |
| 禁用按钮观测次数 | 244 | 129 | 373 |
| 有 visibleReasons 的禁用按钮 | 40 | 14 | 54 |
| 上述原因关联 aria-describedby | 40 | 14 | 54 |

表格检查对应 [ui_refinement_geometry.cjs](/Users/lurenxing/GitHub/----/tests/workbench/ui_refinement_geometry.cjs:78) 的实际 DOM 观测：检查 caption 存在及 th 是否有 scope 属性；不是读屏软件实测，也不单独证明每个 scope 值、表头关联或所有未来弹窗都正确。

54 次原因观测包括“请先勾选记录”“物料已被批次需求引用，不能删除”“请先完成排产检查，再确认本次计算”“工序已完工，请补齐原记录或明确更正”等。均能沿 aria-describedby 找到探针判为可见的说明节点，不只是 title。

其余 319 次禁用按钮没有 visibleReasons 记录，包含分页边界、未选择对象、弹窗打开时背景锁定等情形。此记录不能被写成“全部禁用按钮都有就地原因”，也不能仅凭该计数认定这些按钮全部存在缺陷。长原因是否完整换行及键盘焦点行为由下方独立测试补证。探针的 visible 条件使用非零几何及 display/visibility，不等同于每条原因已在当前视口内完整读到。

## 独立键盘与焦点证据

以下证据与静态矩阵分别记录；没有把截图或 Canvas 的 tabIndex 观测当作键盘操作。

- [共享控件结果](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-shared-controls-iraw_adm/shared-controls-result.json) 为真实 Chromium 109 的源码组件 fixture，11 项交互均 passed，errors/external 为空。涵盖字段 aria 与首错焦点、错误去重、就地禁用原因关联、窄操作列长原因换行、自动预览不抢焦点、详情标题焦点与关闭后返回、Modal 草稿确认及取消。逐项比对其 13 个源码/CSS 哈希，均与 final54 冻结 manifest 的来源记录一致；这支持同源共享组件行为，不将 fixture 冒充完整应用所有入口验收。详情背景见 [共享详情验收](/Users/lurenxing/GitHub/----/.codestable/features/2026-09-12-wbui-detail-panel/wbui-detail-panel-acceptance.md:9)。
- [最新实际甘特键盘结果](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-wbui-actual-keyboard-k_4e0gyd/result.json) 为 synthetic component reports，passed=true，errors=[]。真实操作覆盖 65 个 marks、第二条报工、零时长点与末条报工、Home/End 和四方向键、Enter 激活、Tab 退出、指针焦点与坐标保持、计划/剩余标记、空集合不可选及 DTO 不变。其 8 个源码/运行时输入哈希均与 final54 冻结 manifest 一致；未测试生产数据库或 Win7 硬件。
- 旧键盘结果 `aps-wbui-actual-keyboard-289qehp0/result.json` 的 ActualGanttWindow.js 哈希不同，不能作为最终绑定证据；本索引已改用上述 `k_4e0gyd`，其 Window 哈希为 `710f78d29b390b32b3aaa916036a874dd96aaa22dbdc1a071b53d668aad74a44`。
- [最终点工序补验日志](/tmp/aps-wbui-implementation-20260912/actual-final-point.log) 记录 2 passed，主线程用于接续中间轮分钟格式探针修订；它是补充日志，不能替代上面的按源绑定键盘结果。

矩阵另有 13 次 Canvas 观测，标签为“真实安排时间分布”、tabIndex=-1；该记录本身既不证明不可达，也不证明全部标记可达。可操作集合的遍历结论只来自明确执行过按键的测试。G6 是可见文本中的长十六进制检查，不能单独升级为所有 aria-label 已完整审查。

## 状态与尚待归并

本项状态保留 in-progress，不修改原 checklist 或 roadmap。全仓质量门禁仍在主线程运行，最终总证据链接及完成状态由主线程补齐；这里没有代填 gate 通过。当前矩阵与同源组件证据来自 dirty 工作区的指定构建，不是 clean-worktree proof，也不替代 Win7 发布验收。


## 当前18bc构建补验

`evidence/workbench-ui/2026-09-12-final/browser-18bc/report.json` 在60页面和8交互状态记录80次表格观测，caption全部存在，missingScope全部为空；54次带辅助描述关联的业务禁用说明均可见。373次禁用控件观测还包含由页码或字段上下文解释的分页等控件，不将它们计为373条业务原因。该矩阵与独立UI门禁绑定18bc构建及350个输入，零错误、零豁免。原65标记键盘与焦点回归保留原域内证据；完整质量门禁由总验收独立记录。
