---
doc_type: issue-fix
slug: wbui-plan-selection-restore
status: fixed
created: 2026-09-12
summary: 初始选中任务在关系定位重读时被重复恢复，覆盖用户明确选择的前序任务。
tags: [workbench, plan, navigation, regression]
---

# 计划选中任务恢复修复

完整规划整壳验收在 `dbcec096fa3b76d9418c7066f6cb14f75da787848ba512b93d453d2af6d3aa9b` 构建上实际复现：从正式 v5 的工序 40 点击当前窗口外的前序，服务正确返回同一正式计划的全部 13 道安排，界面最终却选中了旧工序 10，未选中前序工序 30。原业务断言保留，未改成允许任意任务。

`PlanWorkspace.jsx` 原来的两个 effect 在同一轮完整数据返回时先设置关系目标，再依据 `initialContext.selected_task_ref` 设置旧任务。页签现在携带完整页面上下文，旧初始任务因此重新覆盖用户的关系定位。此问题有真实 UI 及严格引用证据，不属于测试定位器改名。

修复只修改 `PlanWorkspace.jsx` 的恢复生命周期：初始任务引用在首次有效读取时消费一次；明确的关系目标优先。显式选择计划、任务、关系、应用范围或切换完整计划会结束初始恢复意图。初次读取失败后仍保留尚未完成的合法恢复，允许用户按原范围明确重读；目标不在当前范围内或完整计划中时显示明确原因，不扩大范围、不回填旧任务。

产品文件 SHA-256 从 `6eef8832750361733210fd4a8a3f42c9759cabe542ca8ac66b388cb4269e133f` 变为 `779f268da227e71d6421bc3b6a87002e5ffbbd28ca5defcd461df89b5d7318c9`。原文件副本与真实失败记录位于 `/tmp/aps-wbui-implementation-20260912/planning-adapt-20260913a/PlanWorkspace.before.jsx`、`plan-selection-product-reproduction.json`。

## 定点验证

在真实 Chromium 109 中，通过现有首屏 probe 编译当前组件源码，补充合法初始恢复后定位窗口外前序、未知初始目标、范围外初始目标及完整计划缺失关系目标四个生命周期场景。所有夹具均先通过真实 `PlanProcessOrder.validate`，并核对精确选中引用、同一计划读取范围及零写调用。

相同三个测试文件的 SHA-256 未变化，旧源码四场景全部失败；产品修复后四场景全部通过。原有六个首屏几何场景保留。pytest 红灯 `1 failed / 5.27s`，绿灯 `1 passed / 2.78s`。对照记录：`/tmp/aps-wbui-plan-selection-lifecycle-20260912/four-case-red-green.json`。

追加的第五场验证初次读取失败后，用户按原范围明确重试仍恢复合法任务；五场与原六个几何场景为 `1 passed / 3.00s`。限定入口自查又锁定“首读失败后显式切换完整计划”需要取消原恢复意图，第六场在中间源码上单独报错，另外五场及六个几何场景通过（`1 failed / 3.37s`）。补齐完整计划按钮的同一生命周期处理后，相同测试最终为 `1 passed / 3.19s`，六个生命周期与六个几何场景全部通过。证据：`/tmp/aps-wbui-plan-selection-lifecycle-20260912/full-range-red-green.json`、`final-evidence.json`。

## 整壳测试适配与证据边界

同轮旧整壳测试按实际页面适配预检标题、目录折叠、表格语义、页签、业务名称及固定小数显示。原动作、指定计划与候选、范围、只读 HTTP、导出、原数据保留和重启断言均保留。`dbcec096…` 隔离副本阶段已有：候选来源与预检返回 `8 passed`，只读规划 `4 passed`，required 只读与冲突分支 `8 passed`，基础整壳 `25 passed`（92 个浏览器场景）。这些结果绑定修复前构建，不能冒充后续新构建的最终验证。

后续真实完整流程又适配三处未保存输入确认：拒绝离开后分别保留 13:15、13:30、13:00 的草稿输入，再由用户动作明确放弃；stale-write 场景额外核对拒绝与放弃前后 77 表快照不变。新进程的历史计划及可查看旧场景选择改用真实点击，并以目录收起、原 `plan_ref`、完整 `tasks` 和 caption 核对结果，避免在选择后已卸载的 radio 上等待 `check()` 收尾。没有减少原业务动作或绕过确认。

## 最终完整规划验证

最终构建为 `18bc07cb5aef60b42feeb1283f9a60c026a9060fa5d105c2d63071ff848c40fc`。在主线程冻结副本运行整个 `tests/workbench/test_final_planning_browser.py`：**4 passed / 248.34s，0 failed / error / skipped**，覆盖 1920、1392 两种宽度和浅、深两种主题。

每组均完成 125 个原业务动作及 9 个新进程恢复动作，77 表独立 oracle 的 `errors=[]`；正式 v5/v6、四候选、同一计划的完整 13 道安排、窗口外前序工序 30、原数据保留、浏览器实际 POST 与服务记录一致、SQLite 完整性和外键检查通过。每组生成 76 张截图与 4 个下载产物。两个主机进程不同，重启浏览器全程只读，加载源码及资产均无变化。

完整证据：`/tmp/aps-wbui-implementation-20260912/planning-adapt-20260913a/full-planning-final-evidence.json`；原日志与 JUnit 为同目录 `18bc-full-planning-final.log`、`18bc-full-planning-final.xml`。旧构建阶段的局部通过及中间失败仍分别保留，不与本次完整通过合并计数。

本子任务未修改 `PlanGantt`、样式或 registry，未构建共享 static，未暂存或提交 root 内容；这些是明确源码与构建上的定点及完整规划验证，不是 root clean-worktree proof。最终整仓质量门禁由主线程统一执行。
