---
doc_type: feature-acceptance
slug: wbui-tokens-states
status: "completed-with-validation-limit"
created: 2026-09-12
feature: 2026-09-12-wbui-tokens-states
roadmap: workbench-ui-refinement
roadmap_item: wbui-tokens-states
summary: "共享样式令牌、字号、严重度及交互状态实现已收尾；验收结论为completed-with-validation-limit。"
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

# 令牌与交互态局部验收

实现范围：应用 CSS 文件 00-tokens、10-shell、20-controls、21-table-frame、30-workspaces；WorkbenchControlStyles 静态 CSS 迁移，运行时只维护主题图标变量；WorkbenchCaption 的动态 style 移入 shell 并将真实顶栏固定 60px。build.py 严格读取 styles 清单，将输入和发布文件来源哈希写入 manifest，发布前复核 CSS 和清单未变化。

表格采用有视口预算的内部滚动框，表头 top:0，关键列和操作列固定。隔离 stacking context 中表头整体高于表体，角表头又高于横滚普通表头，避免仅几何位置正确却被遮盖。密度只改变 padding；radio 未选中为空心；低分辨率侧栏保留全部项。

## 实测证据

- `tests/workbench/app_styles_geometry_probe.cjs`：Chromium 109，1280×720 / 1366×768 / 1920×1080 × light/dark 共 6 组合通过。包含根页面宽度、60px 顶栏、14 项/6 组侧栏末项 bottom=678px、内部纵滚表头、横滚左右列、真实点击操作按钮、左右角 elementFromPoint 遮挡检测、radio空心、日期主题图标、紧凑密度字号不变、hidden属性优先级及普通弹窗/草稿守卫遮挡关系。
- `tests/workbench/control_style_probe.cjs`：56/56 通过，无浏览器错误和外部请求。覆盖默认/hover/active/disabled/focus、checkbox/radio、下拉日期时间图标、文件输入、只读输入和保留语义控件。
- 构建/显式清单测试 84 passed；入口测试 17 passed。资产全量构建测试初次在隔离/tmp镜像因并行未完成的 FieldEditorFields.jsx 缺失停在fixture初始化；源码齐后进一步暴露 WorkbenchGuards → ResourceControls 的脚本装载顺序，主线程已修复装载顺序并完成首次构建；后续实际结果见 CSS 层 feature 的 `2026-09-12-first-build-verification.md`。
- CSS 静态门禁 `node tests/workbench-app-styles.cjs` 全目录通过；`git diff --check` 通过。
- 控件证据 `/tmp/aps-wbui-control-styles-20260912/`；最终样式几何证据 `/tmp/aps-wbui-style-foundation-20260912-final/app-styles-geometry.json`。报告保存来源哈希、导入资源 build_id 和浏览器版本。

## 证据边界与交接

这是当前 CSS 源码叠加冻结原型资源的隔离组件验证，`global_build:false`，不是真实业务工作区终验。未改领域API，未写业务数据，未跑 Win7 真机。仓库已有其他调度和本轮并行改动，不能宣称 clean-worktree proof。

主线程收齐工作区来源与 styles 清单后，统一构建 static/workbench，再跑 test_assets_build.py、test_validate_dist_static_payload.py、test_ui_contract_component_tokens.py、真实工作区几何与总门禁。批次真实页面、基础资料首屏重叠和各工作区宽度由对应 owner/总验收补齐；旧迁移截图不能直接复用为新build验收。

首次集成构建补验：资产/入口/发布payload/UI token组合50 passed，唯一失败为正在并行修改的CSS源码与首次static版本不一致；secondary-copy真实24页面案例全部通过、无写请求和业务数据变化。严格来源绑定保持，仍待最终统一build后收口。
