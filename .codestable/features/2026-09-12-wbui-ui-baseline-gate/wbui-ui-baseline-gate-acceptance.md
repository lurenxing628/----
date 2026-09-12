---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-ui-baseline-gate
status: "completed-with-validation-limit"
created: 2026-09-12
summary: "工作台基线、完整几何矩阵及显式UI门禁接线实现已收尾；验收结论为completed-with-validation-limit。"
tags: [workbench, ui, evidence, gate]
roadmap: workbench-ui-refinement
roadmap_item: wbui-ui-baseline-gate
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 界面基线与验收门禁

## 已完成的实现和验证

- `ui_refinement_server.py` 在本轮独立临时根目录创建测试数据库；fixture 只在该目录播种 30 个批次、真实报工和待补材料。实际应用工厂、路由和本地构建资源用于采集，未打开生产数据库进行本项验证。
- 修改前构建 `7175f2b1dfee7a583f9f3d43a43f88e3999f6fb2757fdda4ec5647430e161621` 已冻结。普通基线采集 60 个页面组合；补充丰富数据基线采集 60 个页面和 8 个交互状态。旧基线的失败保留原 owner/条目/移除条件，不作为最终通过证据。
- 当前构建 `54c40205c9063d08147de7ff516d3bfe0430f314ab336712b37c4060f1e491f5`：Chromium `109.0.5414.46`，15 视图 × 1280×720/1366×768 × 浅/深色，共 60 个页面，8 个交互状态及 4 组密度切换全部完成；G1–G6 和局部裁切、重叠、点击检查无失败，脚本/网络错误为空。
- 正式证据门禁已通过：`ui_refinement_gate.py --evidence-dir /tmp/aps-wbui-implementation-20260912/final54-ui` 返回 `passed=true`、`hard_errors=[]`、`failed_measurements=0`、`backend_source_drift=[]`。该入口同时执行样式合同和显式浏览器合同，最终证据无豁免。
- 导航、节点合同、证据正反测试及 daily opt-in/registry 测试合计 `56 passed in 70.76s`。其中证据测试明确拒绝缺页面、缺断言、旧构建、错误浏览器、主题错配、变动的 boot/源码/模板/探针、残余豁免和不完整交互；不会把采集失败或跳过当作通过。
- 新门禁接入 `run_daily_quality_gate.py --workbench-ui-evidence DIR`；默认不传该选项时，原有真实浏览器 manual/CI skip 政策保持。非浏览器共享合同登记到 required scope，浏览器证据仍要求显式执行。

## 可追溯产物

- 最终矩阵与校验：`evidence/workbench-ui/2026-09-12-final/browser/report.json`、`verification.json`、`asset-manifest.json` 和同目录 PNG/boot。
- 改前基线：`evidence/workbench-ui/2026-09-12-final/baseline-current/`、`baseline-rich/`。
- 首次源清单、原始状态及最终构建记录保存在该 evidence 根目录。最终矩阵逐文件绑定 build 输入、发布资源、HTML 模板、UI Python 入口和采集脚本哈希；非 UI 后端漂移单独记录。

## 收口边界

整仓质量门禁与带本项 opt-in 的 daily gate 尚在运行，最终结果由路线图统一验收记录回填。原工作区存在其他任务的暂存/未暂存改动；隔离副本即使通过门禁也不属于最终 HEAD 的 clean-worktree proof。本项不新增 Win7 发布或旧界面退役验收。
