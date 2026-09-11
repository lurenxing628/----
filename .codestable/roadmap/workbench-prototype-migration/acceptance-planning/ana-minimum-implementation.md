# ANA001/003 最小只读补齐

- Main 已明确授权连续实施这六个冻结动作，不再等待 GO：`WBP-ANA-001.metrics/unavailable/tradeoffs`、`WBP-ANA-003.delivery/history/batch-gantt`。146 个动作分母不变，旧通过证据不覆盖本次新实现。
- 当前状态：授权实现已完成，后续固定源完整入口 16 passed（含四组合、F5/newPID），定点/复用服务回归 46 passed。Main V 和最终合并源统一门禁仍未完成；收敛短交接见 `ana-handoff.md`，旧证明不回写。
- 实现期检查：首批真实数据库定点测试 14 passed，定点 Pyright 0 errors / 0 warnings，六份前端源码按仓库 Babel 7.29.0 / Chrome109 配置通过语法编译。
- 定点记录：`/tmp/aps-final-d-ana-service-two.xml`。首轮仅测试种子忘记提交自身事务，已修正种子并完整重跑；没有改受理事务边界。

## 数据范围

- 新 `core/models/workbench_run_analysis.py` 与 `core/services/workbench/run_candidate_analysis.py` 固定读取原永久候选的完整 workspace、完整受理 baseline 和完整受理批次。复用 `dashboard_candidate_comparison` 的交付投影与摘要函数，不复制 F 的交付推算。
- 四指标与甘特搜索、日期或批次切片独立。调整/换设备以原永久 operation_ref 去重；缺基线、分段不能一一核对、资源身份未知保留 `value=null`、已知小计、未知数及原因。换型不作为换设备数。
- 取舍只陈述候选减基线的可证变化，不生成推荐、收益或成本结论。
- 新 `core/services/workbench/run_candidate_history.py` 只读取该候选采用 action/context 的原回执，并复用采用基线证据链核对原正式版本、候选/运行、审计和完整安排。未采用可为空；损坏不变为空历史；原版本不可核对时仍保留原回执并禁用原计划按钮。不使用 Trial 记录充数。
- GET 路径：`/api/workbench/v1/scheduling/candidates/<candidate_ref>/analysis`、`/adoptions`。拒绝范围参数及错误命名空间，不接受 POST，不安装结构、不发写票据、不生成历史。沿 `web/routes/workbench/run_candidates.py` 的现有注册入口接入。

## 页面与集成

- 四份原有 `RunCandidateWorkspace/Controls/API/Model` 加两个同职责叶子：`RunCandidateAnalysisAPI.js`、`RunCandidateAnalysis.jsx`。
- Main 负责共享 build-order：`RunCandidateAPI -> RunCandidateAnalysisAPI`；`RunCandidateControls + RunCandidateModel -> RunCandidateAnalysis.jsx -> RunCandidateWorkspace`。D 不修改 Main 共享构建/测试注册文件。
- 批次按钮只带原 `run_ref/candidate_ref/batch_ref` 进入完整批次甘特；原采用计划按钮只带回执原 `plan_ref`，不带候选身份、不选最新计划。
- 定点测试新增 `test_final_planning_analysis.py`、`test_final_planning_analysis_history.py`；Main 后续测试注册应纳入同属候选只读范围。完整入口探针仍在扩展，本记录不把单测冒充六动作完整 K/P/V 通过。

## 既有签核

- P003 两动作 Main V 已签 `../round2-main-v-D-p003.json`，本轮核对 SHA-256 为 `3b336969b115b73c8587fd969a56db9c300c004ca5d2735628582b40a3f1aa7a`。
- 仅 `WBP-GANTT-003.predecessors` 与 `WBP-GANTT-004.trial-link` 使用该签核。其 20 full-page + 4 viewport 图不替代 ANA 或其他动作的视觉证据。
