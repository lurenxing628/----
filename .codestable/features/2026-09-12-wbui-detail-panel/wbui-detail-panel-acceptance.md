---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-detail-panel
status: "completed-with-validation-limit"
summary: "共享详情面板的显示、焦点移入及关闭返回实现已收尾；验收结论为completed-with-validation-limit。"
roadmap: workbench-ui-refinement
roadmap_item: wbui-detail-panel
tags:
- workbench
- ui
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 针对性验收

## 最终构建补验（2026-09-12）

本节为最新结果，补齐下方中间轮的导入阻断、源码漂移和未构建边界。三个pytest入口均实际执行成功：**3 passed in 75.15s**。

```bash
.venv/bin/python -m pytest -q tests/workbench/test_resource_detail_layout.py tests/workbench/test_resource_navigation_context.py tests/workbench/test_shared_controls_widgets.py -s --basetemp=/tmp/aps-wbui-shared-final-bind-20260912
```

- 固定构建：`622d8759b3adb49919af98d2bf729585cec1085c633532098200cfa61533f1ee`。开始与结束均核对asset-manifest；结束再次比对导航和共享探针记录的全部源码/CSS哈希，均与当前现场一致。
- 资源详情成包验证：真实Chromium `109.0.5414.46`，48个场景、1068条断言、96张截图通过；覆盖1920×1080、1392×924与light/dark。结果：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-resource-detail-layout-a7c0djv3/resource-detail-layout-result.json`。
- 资源导航源码验证：92个场景、32张截图通过；浏览器错误、外部请求为空，末尾源码绑定检查通过。结果：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-resource-navigation-z-6r066f5v/navigation-result.json`。
- 共享控件最终pytest wrapper：11项交互通过；实际执行而非跳过，不再被scheduler导入阻断。结果：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-shared-controls-iraw_adm/shared-controls-result.json`。

以上是同一冻结现场上的组件、布局和导航验收；全仓质量门禁、15视图整体几何及Win7发布验收仍按主线程总记录区分，不将dirty工作区写成clean proof。

覆盖无.plana祖先的真实应用容器、1366宽右侧列、1100宽整行详情、标题首次和detailKey切换聚焦、Esc退出以及触发元素焦点恢复；内容视窗外时主动滚到标题可见位置；自动首条预览显式autoFocus=false时不抢焦点、不滚离首屏。

- 实施阶段源组件探针：`tests/workbench/shared_controls_probe.cjs`，真实Chromium `109.0.5414.46`，11项交互通过；没有浏览器错误或外部请求。结果 `/tmp/aps-wbui-shared-controls-final3-20260912/shared-controls-result.json`，执行后逐一核对其中所有源文件哈希与现场一致。
- 长禁用原因新增反例先在旧样式失败（继承操作列nowrap导致单行裁切），补显式换行后通过逐文本rect边界检查；前后证据分别在 `/tmp/aps-wbui-shared-controls-reason-before-20260912/` 与 `final3` 目录。`reason-narrow.png` 实测完整多行显示；未用overflow隐藏消除信号。
- 资源编辑器隔离探针：`resource_forms_probe.cjs`，84项检查、32张截图通过，结果 `/tmp/aps-wbui-shared-forms3-20260912/forms-result.json`；库存/弹窗探针92项检查通过，结果 `/tmp/aps-wbui-shared-stock4-20260912/stock-modal-result.json`。它们是各自源快照的组件证据；后续最后的通用长原因样式、跳页名称及自动预览焦点由final3覆盖，不冒充整包证据。
- `git diff --check`与新pytest wrapper的Ruff检查通过。

## 中间轮记录和剩余边界

- pytest wrapper较早轮通过；此前中间一轮在autouse setup被已有并行scheduler改动的ImportError阻断，尚未运行本测试：`optimizer_multi_start_dedup.py`导入`native_multi_start_calendar_snapshot`失败。当时共享组件结果来自同一个CJS探针的直接Node运行，没有修改或绕过业务代码。
- 此前中间轮`test_resource_navigation_context.py`的真实浏览器92项交互、32张截图均通过，错误/外部请求为空；但结尾源哈希检查发现运行期间`WorkbenchFormat.js`改变，pytest整体失败。这份只证明其冻结快照，不声明当前绑定。
- 此前`resource_detail_layout_probe.cjs`已补新共享依赖，当时等待主线程最终统一构建后运行；当时资源源文件与首个build_id不一致，不用旧产物冒充新UI验收。
- 这是dirty并行工作区的针对性证据。总门禁和完整工作台几何由主线程总记录说明；本项build_id与最终源码绑定已由本节补验确认。未执行Win7硬件验收；不提交、不修改领域API或生产数据库。

## 最终共享源摘要

- `frontend/workbench/app/WorkbenchDetailPanel.jsx`：`48e21c661120c86c7aa127f7075eeea9ebe208fdbad7227547c985d26c8cd5c6`
- `frontend/workbench/app/styles/22-shared-controls.css`：`bc421e76d23d8c8b9c86cadcd6f66015e010840593093da9544e57fa1221dfb3`
