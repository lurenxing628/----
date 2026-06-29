# 修复执行提示词 · 排产优化器作用点错位(item 6/7/8)

> 用法:把本文件内容整段交给执行 Agent。它自包含,但要求 Agent 先读审计文档再动手。

---

你是 APS 排产系统的修复工程师。本仓库是**单机离线**软件,目标机 **Win7 x64 / Python 3.8 / 无网络**。请按下面的清单修复一组已确诊的排产优化器缺陷。所有结论与改动都要带 `文件:行号`,失败要明确暴露,不要包装成成功。

## 0. 先读 + 起步规则(必做,不可跳过)

1. 先读审计报告:`.codestable/audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md`(根因、证据、分路径图景、P0–P6 治理清单全在里面)。
2. 读 `.codestable/attention.md` 和 `.codestable/reference/system-overview.md`。
3. 动手前 `git status --short`,分清已有改动与本轮改动;**不要回退/覆盖** `.codestable/architecture/`、`.codestable/checkup/`、`tools/scan_import_cycles.py`、`.codestable/audits/2026-06-28-circular-imports/` 等**非本轮**文件(那是别的任务的)。本轮已存在的产物:`tests/_scripts_e2e/probe_localsearch_actuator.py`、`tests/algorithm/test_localsearch_batch_order_actuator.py`、`tests/_scripts_e2e/benchmark_smtwt_localsearch.py`(验收要用,别删)。
4. 改任何函数前,用 `python3 -m tools.symbol_locator callers <fn>` / `callees <fn>` 查影响面。
5. 全局原则:**按根因修,不过度兜底、不静默回退、不吞错**;不顺手重构无关模块;不引入新依赖/新运行时;APS 主链继续兼容 Win7/py38/离线。

## 1. 验收基线(改之前先各跑一遍,记下数字)

```bash
# A. SGS 死键 vs batch_order 有效(应当 4 passed)
python3 -m pytest tests/algorithm/test_localsearch_batch_order_actuator.py -q
# B. 全排列探针(SGS 三规则 distinct=1,batch_order distinct>1)
python3 tests/_scripts_e2e/probe_localsearch_actuator.py
# C. SMTWT 250 局搜实测(当前:sgs 改进 0/250、batch_order 改进 165/250)
python3 tests/_scripts_e2e/benchmark_smtwt_localsearch.py
```

**总验收目标**:修完 P0 后,C 脚本里 **sgs 模式的"局搜改进个数"必须 > 0**(从 0/250 提升),且 gap 真实缩小;其余 P 各有独立验证。

---

## P0 · 作用点错位(根因,架构级 —— 先设计后实现)

- **缺陷**:GRASP/IG 与业务邻域的搜索旋钮主要是 `batch_order`,而 `batch_order` 在 SGS 是 `build_dispatch_key`(`core/algorithms/dispatch_rules.py:87-95`)的第 6 位 tie-break,前面压着 `score_penalty`(`sgs_scoring.py:71`)、`primary`、`time_left_h` 等连续量,**实测在 SGS 下完全改不动结果**(`benchmark_smtwt_localsearch.py`:sgs 改进 0/250)。默认 `graph_analysis_mode=on` 让多数候选走 sgs,GRASP/IG 又硬编码 sgs 解码(`optimizer_grasp_ig_candidates.py:74`)→ 大量算力空烧。
- **不要这样修**:不要简单地把默认 dispatch_mode 从 sgs 切走、或关掉 graph(那是回避不是治理);不要给空烧加缓存式补丁。
- **要这样修(先出方案)**:这是行为级架构改动,**先走 `cs-issue`**(report → analyze → fix)或 `cs-feat`,把方案写清楚交用户拍板,再实现。候选方向(择一或组合,在 analyze 阶段评估):
  - **方向 A**:让搜索作用在真正驱动 SGS 选择的维度 —— `dispatch_rule` 组合切换、primary 规则参数、或对 SGS ready-queue / 资源选择做扰动(让邻域产出这些 move,而不是只产 `batch_order`)。
  - **方向 B**:GRASP/IG 不再硬编码 sgs 解码(`optimizer_grasp_ig_candidates.py:74`);按候选实际派工模式解码,batch_order 候选用 batch_order 解码(有效路径),避免在 sgs 下空烧。
  - **方向 C**:明确"批次顺序邻域只服务 batch_order 派工";SGS 路径改用对 SGS 有杠杆的邻域。同时处理 P5(图 ready 路径用 `sort_key_by_op_id`,`schedule_graph_dispatch_context.py:193-202`、`sgs_graph.py:267-268`,根本不消费候选 batch_order)。
- **建议**:用 subagent 并行做影响面分析(symbol_locator 调用链)+ 方案对抗评估。
- **验收**:`benchmark_smtwt_localsearch.py` 的 sgs 模式改进数 > 0、gap 真实缩小;且新增一个用真实 `GreedyScheduler.schedule` 的端到端测试断言 sgs 路径下优化后 score 严格优于 baseline。

---

## P1 · 补真实有效性测试(高优先,可与 P0 并行)

- **缺陷**:item 6/7/8 三套合同测试全 stub 掉真实 `GreedyScheduler.schedule`,改善是假 `schedule_fn` 写死喂的,无法发现"退化成 no-op"。文件:`tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py`、`test_optimizer_business_neighborhood_registry_contract.py`、`test_optimizer_vns_sa_local_search_contract.py`。
- **步骤**:参照 `tests/algorithm/test_localsearch_batch_order_actuator.py` 的写法(用 `optimizer_proof_oracle` 的 `_operation_object`/`batch_objects`/`_ContinuousCalendar`/`_default_config` + 真实 `GreedyScheduler`),为 GRASP/IG、业务邻域、VNS 各补**至少一个端到端用例**:构造一个 batch_order 模式下可改进的小实例,断言"优化后 objective score 严格优于 baseline"。
- **验收**:把对应实现临时改成 no-op(本地试)时测试变红;恢复后变绿。

## P2 · acceptance 尺度错配(threshold / record_to_record)

- **缺陷**:`DEFAULT_THRESHOLD=1.0`(`core/services/scheduler/run/optimizer_acceptance.py:24`)直接与 `_score_delta`(`:197-206`)比,而 score 首分量是 `failed_ops`(硬约束整数,`optimizer_local_search_candidate_eval.py:66`)。显式选 threshold/RTR 时早期会把"多失败 1 道工序"的更差解接受为 current。
- **步骤**:在 `decide_acceptance`(`:67-131`)的 threshold / record_to_record 分支,**先判 `failed_ops` 维度零容差** —— 候选 `failed_ops` 比参照大就直接拒,阈值只作用于目标分量(从 score 第 2 位起)。改 `_score_delta` 或在分支里加前置判断,二选一,保持单一真相源。
- **验收**:补测试锁"threshold/RTR 下候选 failed_ops > current 必拒";`improve_only` 行为不变。

## P3 · positive_count 裸吞异常

- **缺陷**:`core/services/scheduler/run/optimizer_neighborhood_move_support.py:31-35` `except Exception: return 0` 吞掉一切异常(只为算诊断字段 chain_node_count)。
- **步骤**:去掉裸 `try` 或把 `except Exception` 收窄为 `except TypeError`(`results` 是内部 list,`len()` 不该抛;真抛说明上游类型坏了,应 fail-loud)。
- **验收**:补一个用例:传入异常输入时不再静默返回 0。

## P4 · resource_alternative 虚假有效移动

- **缺陷**:`core/services/scheduler/run/optimizer_neighborhood_moves.py:181-200`,旧 `pair_rank ≤ -1` 时 `min(old, -1)` 无真实变化,却仍报 `changed_decision_count=1`。
- **步骤**:仅当 `min(old_rank, -1) != old_rank`(即真的改了)才产有效 move;否则返回 `noop_move(RESOURCE_ALTERNATIVE, reason="resource_pair_rank_unchanged", ...)`。
- **验收**:补测试锁"旧 rank 已 ≤ -1 时返回 noop、changed=0"。

## P5 · 图 ready 路径不走候选 batch_order

- **缺陷**:图 ready 排序用图自己的 `sort_key_by_op_id`(`schedule_graph_dispatch_context.py:193-202`、`sgs_graph.py:267-268`),不消费候选 batch_order → 批次顺序邻域在图路径完全无效。
- **步骤**:并入 P0 设计一起决策(图路径下批次顺序邻域是否还保留、或改作用点)。**不要**单独硬塞 batch_order 进图排序而破坏图语义。
- **验收**:在 P0 方案里明确图路径邻域行为,文档化;不再让无效旋钮对外显示为"有效"。

## P6 · 解码后去重不挡空烧(性能)

- **缺陷**:same_fingerprint 去重发生在完整 SGS 解码之后(`optimizer_grasp_ig_candidates.py:292-328` + `optimizer_search_report.py:271-276`),挡不住重复候选的解码成本。
- **步骤**:在解码**前**按 `decision_fingerprint` 去重 candidate specs(`build_grasp_ig_candidate_specs` 产出后、解码前过一遍),保留 decoded_output 去重做最终口径。
- **验收**:补测试锁"相同 decision 的候选不再各付一次完整解码"(可统计 schedule_fn 调用次数)。

---

## 9. 收尾(全部改完)

1. 跑第 1 节三个验收脚本,确认 **sgs 局搜改进数 > 0**、相关测试全绿。
2. 跑质量门禁:`python3 scripts/run_quality_gate.py`(不能跑要说明原因)。
3. 更新审计文档 `index.md` 的 status(open → 对应进度)与各 P 项状态。
4. 若 P0 改动了 roadmap 契约,同步 `.codestable/roadmap/scheduler-global-optimizer/`(items.yaml / roadmap.md)。
5. 汇报:改了哪些文件、跑了哪些测试/门禁、还有哪些未提交、下一步建议。**只有工作区干净且最终 HEAD 上跑过门禁,才能说 clean-worktree proof。**

## 红线复述

- 不过度兜底、不静默回退、不吞错;repair/候选失败要 fail-loud 或明确 candidate_rejected,不能假装成功。
- public/OperationLogs/导出/size guard 不得泄漏 raw move、内部 op/resource id、fingerprint hash、随机数 draw(沿用现有 diagnostics 边界)。
- 不引入 OR-Tools 为主引擎、不引入 NumPy/云服务等新重依赖;保持 Win7/py38/离线。
- P0/P5 属架构级,先出方案给用户确认再改,不硬冲。
