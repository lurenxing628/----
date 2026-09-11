# 候选逐批交付风险最小复用方案

> 状态：本提案已获 Main 明确授权并实施；下文“当前缺口”“申请”保留提案时背景，不代表仍待授权。验收结论见文末，不能把实现状态当成全站通过。

> 文末的 72 动作是较早快照。后续完整入口和 D-P001..004 修复以同目录 p001-p004-fix-note.md、open-findings.md 为准；不能把旧进度或旧暂停状态当成当前结论。

## 当前缺口

`WorkbenchRunCandidateQueryService.workspace` 已验证并返回真实持久候选任务、受理时 `GenerationFacts`、完整性与未排项，但没有逐批交付投影。候选摘要中的 overdue_count 等指标只覆盖已完成批次，不能替代全批交付结果。

正式计划的 `read_plan_delivery` 会读取当前业务表，不能直接用于历史候选。可复用的是纯计算 `plan_delivery_projection.project_delivery_batch`，其全工序覆盖、交期次日零点边界、未知和部分完工规则应保持不变。

## 申请的后端写集

1. 新增 `core/services/workbench/run_candidate_delivery.py`，只做受理快照到已有纯投影的适配。
2. 修改 `core/services/workbench/run_candidates.py` 的 `workspace`，在过滤前传入已验证完整候选，将投影纳入原响应及 fingerprint。

不新增路由、表、schema，不修改算法/runtime、`project_delivery_batch` 或当前正式计划读取规则。若投影合同需要扩大，再报告具体必要路径，不默认扩大。

## 数据与范围

- 明细使用 `CandidateStore.tasks` 和已通过 `tasks_projection` 完整性、身份、时段与零工时证据校验的全部任务。内部 op_id 由受理快照中 operation_ref 映射得到，不解析或改造永久引用。
- 批次、交期、工艺操作全集、资源标签和身份只使用已验证 hash 的 `GenerationFacts`。不查询或拼接今天的 Batches/BatchOperations/Parts。
- 先计算所选批次的完整候选行，再按当前读取 scope 选批；局部时间窗不截断一个批次的完工依据。无时间的未排项保留在范围中，未安排、被跳过及缺工序不能当成完工。
- 零工时行仅在已有 `CandidatePointReader` 已验证后提供 point 标记；相等起止本身不是合法证据。
- 完整性必须核对受理时该批全部工序，不只核对当前候选输出工序。候选摘要只能提供负向不完整提示，不能填补明细。
- 基础字段缺失、无法映射或旧记录证据不全，要么沿原 corrupt 拒绝，要么明确标未知及原因；不默认为零风险，不降级到当前正式计划。

## 建议返回合同

- 追加 `delivery_risks`：`candidate_ref`、当前 scope、`items`、完整范围数量、计算依据和未知原因。沿用现有逐批投影字段，不伪造正式 version。
- `basis` 明确为受理时业务快照、完整候选安排、工厂本地时间；不是实际完工/发货/根因。
- 末端工序由完整已验证明细中与真实全批 planned_finish 相等的行得到，返回所有并列末端的原 row_ref/operation_ref。若全批不完整则不提供可误认成全批完工的末端跳转。
- 响应继续遵守原 `MAX_RESPONSE_BYTES`，超限明确拒绝，不能改门限或静默截断。

## 前端接线

- Main 负责 pages/main 的 delay 入口、全局 caption provider，以及将 `SchedulingWorkspace` 的 view 传给 `RunCandidateWorkspace`。
- D 可改 `PlanWorkspace.jsx` 的 delay 标题/风险优先布局；正式风险仍用现有 `PlanDetailsUI.ProjectionTables`。
- 候选还需 `RunCandidateAPI.js` 验证上述投影与原候选/scope 同源，`RunCandidateControls.jsx` 显示逐批数据，`RunCandidateWorkspace.jsx` 接线和 caption 发布。维持候选非正式状态。
- 不能仅重命名整个候选工作区就宣称 DELAY-001..004 全完成；跨页选择、范围和末端引用须有真实浏览器验证。

## 最小验证

- 完整共同/分件及零工时：逐批 finish 由全批最后任务决定，quantity 与原始 refs 保持不变。
- 缺一道末序、skip、部分候选：未知或不完整，不把部分结束当全批 finish。
- 部分时间窗只含早序：依然使用同批完整候选末序；导出/标签明确读取 scope。
- 生成后修改当前批次交期/工序/资源标签：原候选投影和 refs 不漂移。
- 缺受理事实、损坏 payload、无效/未指定交期：明确拒绝或未知，不用摘要填补。
- 真实完整入口四视口/主题、候选切换、风险定位、刷新及新进程重读；截图由 Main 单独 V 审视。

## 实施与验证进度

- 已按授权新增 `run_candidate_delivery.py`，接入 `run_candidates.py`，实现受理时冻结事实的逐批完整性、交期风险、末端原引用和未知原因；未改算法/runtime、当前正式计划规则、路由/schema 或响应阈值。
- 已在 `RunCandidateAPI.js` 严格校验投影身份、scope、依据、字段与明细引用；候选工作区和控件已接入真实交付表。Main 后续将 `SchedulingWorkspace.jsx` 的 view 传递交给 D 完成。
- `PlanWorkspace.jsx`、`RunCandidateWorkspace.jsx`、`TrialWorkspace.jsx` 已按 Main 共享协议发布真实 caption；正式/候选页面按协议保存当前身份、范围、搜索和选中任务，试调保留原有 target 回调。
- 正式计划风险优先布局复用原投影。联验发现原同父节点重复 key，经 Main 单点授权，三处分别加 `risk-first:`、`gantt:`、`risk-last:` 前缀，保留 snapshot 变化时的重挂载语义。修复后 `PlanWorkspace.jsx` SHA-256：`c8e8139f7a1b3215dfceced802cec04102e979dc95172b78b6b3850c9a58db9a`。
- 服务和合同定点运行：`tests/workbench/test_final_planning_delivery.py`、`test_final_planning_contracts.py`、`test_run_candidate_queries.py`、`test_run_candidate_baseline_queries.py` 合计 `34 passed in 7.77s`，JUnit `/tmp/aps-final-d-delivery-second.xml`；含真实候选响应送入 Node 校验器的一个正例、十个拒绝例。定点 Pyright `0 errors, 0 warnings`，Ruff 检查通过。
- 修复后真实完整入口私有构建 `64b6bfb181a1c4a04c2f3b218de1f8ad9c4a56b306fc3be19e0213899b0bfe77`（215 files、307 inputs）已走通 72 个既有动作及逐字符输入/甘特唯一性检查。当前新增放弃草稿用例仍在收敛，尚未宣布四矩阵全通过、新进程总证明或 Main V 通过。

全部结果为 dirty 工作区的定点证据；完整质量门禁、Git 归档、全站终审由 Main 统筹，本文不冒充 clean-worktree proof。
