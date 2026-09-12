---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-table-density-noise
roadmap: workbench-ui-refinement
roadmap_item: wbui-table-density-noise
status: "completed-with-validation-limit"
summary: "表格密度偏好、状态降噪及零值与未知的区分实现已收尾；验收结论为completed-with-validation-limit。"
tags: [workbench, ui, density]
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 表格密度与降噪验收证据索引

## 最终构建的双密度观测

仅整理已有证据，没有启动新测试或修改产品。[final54-ui/report.json](/tmp/aps-wbui-implementation-20260912/final54-ui/report.json) 绑定构建 `54c40205c9063d08147de7ff516d3bfe0430f314ab336712b37c4060f1e491f5`，浏览器 `109.0.5414.46`；manifest SHA-256 `cbe7910391fc97ef2969e27770bd51d1148fbbe579c803d1760fcb46cea21c39` 与冻结目录实物一致。

报告有 60 个页面状态、8 个交互状态，另包含 4 条 densities 记录。每条比较批次表第一行的 10 个单元格；以下数据均取自这些实际记录。

| 状态 | 舒适行高 | 紧凑行高 | 两种密度字号 | 文字一致 | 紧凑后 G1/操作命中 |
| --- | ---: | ---: | --- | --- | --- |
| batches-1366-768-light | 129px | 121px | 13px | 是 | true / true |
| batches-1366-768-dark | 129px | 121px | 13px | 是 | true / true |
| batches-1280-720-light | 129px | 121px | 13px | 是 | true / true |
| batches-1280-720-dark | 129px | 121px | 13px | 是 | true / true |

四条记录的 ok 均为 true；舒适与紧凑的全部抽样单元格文字、顺序与字号一致，行高减少 8px。G1 在真实双向滚动后记录表头相对框顶部保持、操作按钮命中成功。1366 视口的表框高度为 448px，1280 视口为 400px；操作列没有因切换密度退出可点击区域。

这是双尺寸、双主题下批次表首行的真实抽样，不是所有工作区、所有行或所有内容长度的密度穷举，也不能单独证明刷新保留、跨窗口同步及存储异常行为。矩阵的 80 次表格观测都有 caption、missingScope 为空，54 次禁用按钮观测记录了可见且关联辅助描述的原因；这些语义观测详见 [无障碍验收索引](/Users/lurenxing/GitHub/----/.codestable/features/2026-09-12-wbui-a11y-sweep/wbui-a11y-sweep-acceptance.md:16)，不混入密度行为计数。

## 偏好与交互的独立证据

- [final54-contracts.log](/tmp/aps-wbui-implementation-20260912/final54-contracts.log) 记录主线程最终定向合同 **56 passed in 70.76s**。该轮包含核心导航、证据反例、Node 密度、注册及 opt-in 合同；56 是整组总数，不是 56 条密度测试。
- `test_ui_refinement_node_contracts.py` 纳入 `tests/workbench-density.cjs`。该 Node 合同覆盖默认/保存状态、切换写入、订阅解除、非法值、读取/保存失败的显式错误、pageshow 与 storage 同步、状态副本隔离。这是偏好模块的受控宿主验证，不伪称全部真实浏览器存储环境均测过。
- 导航浏览器合同实际点击顶栏“紧凑表格”，检查 aria-pressed 变化及 html[data-density] 同步。上述最终定向测试提供本轮执行证明；[顶栏早期验收](/Users/lurenxing/GitHub/----/.codestable/features/2026-09-12-wbui-header-controls/wbui-header-controls-acceptance.md:16) 中 `02bd429d...` 的结果保留为历史，不改写成 final54 的截图。
- [共享控件独立结果](/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-shared-controls-iraw_adm/shared-controls-result.json) 的 11 项交互覆盖合法分页档位、页码跳转、游标不虚构总数、空/加载恢复、窄列长原因显示及详情焦点。记录的 13 个源码/CSS 哈希均与 final54 冻结来源匹配。这些结果支持密度变化后仍使用原有共享交互合同，不把控件 fixture 当作所有页面的双密度验证。

## 无现场数据与部分未知的降噪边界

按 [报表域实施记录](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-ui-refinement/implementation-notes/reports-review.md:7)，仅 summary.records 精确为 0 时采用一条“暂无现场数据”横幅；数字 0 保留，部分缺失继续显示“未知”，不能把部分缺失误判为整范围无现场数据。

[报表独立浏览器结果](/tmp/aps-wbui-implementation-20260912/reports-1280-final-v2/report-ui-result.json) 记录 4 组、24 张截图、errors/external 为空；其执行的探针包含单横幅、0 与部分缺失断言。结果明确是捕获 SQLite DTO 的 mock 浏览器交互，style_build_id 为 `02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`，后续共享格式、详情、来源呈现及字号曾有变更，因此只作为该源快照的降噪行为证据，不冒充最终整包回归。最终矩阵的报表页截图本身也不能证明所有“零/未知/部分缺失”反例均执行过。

现场记录去除重复统计、系统和顶栏入口共享同一偏好的实施范围保持原设计；本索引不根据静态截图另行宣称全部业务数据未变。最终总测试与相关领域回归由主线程提供总证据链接后归并。

## 状态

状态保持 in-progress，不修改 checklist 或 roadmap。全仓质量门禁仍在运行，未代填通过或完成；当前证据是 dirty 工作区指定构建及明确标识的独立组件测试，不构成 clean-worktree proof，也不包含 Win7 硬件发布验收。


## 2026-09-12 补验：统一入口与现场去重

当前构建 `18bc07cb5aef60b42feeb1283f9a60c026a9060fa5d105c2d63071ff848c40fc` 的证据覆盖前述对应待验项，不改变旧记录的build归属。

- `evidence/workbench-ui/2026-09-12-final/contracts-18bc.json`：具名运行 `tests/workbench-density.cjs` 通过，包含持久化、错误和同步合同。
- `density-entry-18bc/report.json`：真实Chromium109在系统配置页点击顶栏后，两入口同步为紧凑；系统入口恢复舒适后刷新保留，再选择紧凑刷新也保留。只改变浏览器页面偏好，未点击业务配置保存。
- `browser-18bc/verification.json`：60页面、8交互及4组双密度全部通过，无源漂移、无豁免；80次表格观测的caption和表头scope齐全。
- `final-regressions/final-browser-proof.json` 与 `field-noise-final-v2.log`：现场重复的4项状态统计已移除，7个状态筛选计数及累计工时/部分未知小计保留；完整报工及重启 1 passed，13+5动作、41图、4导出，旧记录和许可4表变更通过。

以上相对证据路径均位于 `evidence/workbench-ui/2026-09-12-final/`。完整质量门禁仍单独等待，不据这些局部结果签发clean proof。
