# 剩余分析合同缺项

- 范围仅限当前剩余 ANA 项；不重开 P003、旧控件或全仓审查。以下保留发现时证据；Main 现已授权最小只读补齐，实施与新验证见 `ana-minimum-implementation.md`，不再把本项列为待批准阻断。
- 证据绑定已通过 R3 源码与完整页面：`/private/tmp/aps-final-d-source-p003-Z3GYfe`。当前 D 产品与该批源的 12 文件核对见 `p003-product-binding.json`；与 Main Esealed/F18 的对应以 Main 的独立绑定为准。

## 四指标与取舍

- 冻结 `WBP-ANA-001` 明确要求预计晚交批数、总拖期 h、调整工序、换设备数及摘要/取舍。
- `RunCandidateAPI.js:24` 的 12 个指标不含调整工序数与换设备工序数；`RunCandidateModel.js:7` 的指标标签也没有这两项。`RunCandidateControls.jsx:45` 仅展示这组候选指标，没有整份候选与冻结基线的四指标汇总或取舍摘要。
- 当前真实页面证据：`ja4vco32/screenshots/final-planning-actions-candidate-comparison.{png,txt,html}`，候选比较列为安排数、超期批次、总拖期、跨度。不能拿这些替代冻结的完整四指标，也不能拿 Trial 页面自己的四指标代替 analysis。
- 直接影响：`WBP-ANA-001.metrics`、`.unavailable`、`.tradeoffs`。其中 metrics 在旧账本曾标 passed，但测试只检查了当前返回和候选点/条，没有核对完整四指标，属于证据覆盖不足，需要补验，不保持完整通过推论。
- 最小涉及文件：`frontend/workbench/app/RunCandidateWorkspace.jsx`、`RunCandidateControls.jsx`、`RunCandidateAPI.js`、`RunCandidateModel.js`。已有 `RunBaselineAPI.js:14,66` 提供单工序冻结 delta，`RunBaselineControls.jsx:4` 目前只在甘特内部按开关读取；可作为真实来源线索，不能直接猜汇总/未知口径。是否需要新的只读汇总 leaf 应先按该完整来源设计，不改 capturer 或调度算法。

## 批次对照与采用历史

- 冻结 `WBP-ANA-003` 要求批次交付/采用记录页签，逐批截止、基准完工、预览完工、变更，以及批次按钮定位甘特。
- `RunCandidateWorkspace.jsx:129` 实际仅有任务安排、未安排明细、交付风险三个页签；`PlanDetailsUI.jsx:96` 的正式计划分析仅为交付风险、资源负荷、资源日历。没有 analysis 的采用记录页签。
- `RunCandidateControls.jsx:109` 当前逐批表只有当前完整候选完工、预计交付与末端工序，不提供基准完工与批次变化对照。末端工序按钮有真实永久 row_ref，但不等于完整的基准/预览批次对照功能。
- 直接影响：`WBP-ANA-003.delivery`、`.history`、`.batch-gantt`。现有 Trial 采用记录页签和单次候选采用回执不能替代该 action 家族。
- 最小涉及文件：`frontend/workbench/app/RunCandidateWorkspace.jsx`、`RunCandidateControls.jsx`；正式计划若承载该入口则涉及 `PlanDetailsUI.jsx`。只读数据层可先核对 `core/services/workbench/run_candidate_baseline.py`、`plan_adoption_baseline.py` 和现有 `trial_adoption_history.py` 的身份范围；后者面向试调场景，不可直接用 candidate_ref/plan_ref 硬套。没有证据证明现有 API 已具备完整候选及正式计划采用历史 DTO，不凭空声明可零改动复用。

以上是本次已授权补齐的依据，不是等待 P003 批准的理由。旧已通过冻结证据不改写，本次增量独立验证并交 Main 集成。
