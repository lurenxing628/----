# 算法层统一估算与派工重构plan深度审查
- 日期: 2026-04-07
- 概述: 对 .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md 进行三轮深度审查
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

## 审查目标

对算法层统一估算与派工重构 plan 进行深度审查，验证：
1. plan 中引用的代码行号、函数签名、数据流是否与实际代码一致
2. 任务拆分与依赖关系是否合理
3. 实现方案是否优雅简洁、无过度兜底或静默回退
4. 是否存在遗漏的影响链或潜在 BUG
5. 约束条件与完成判定是否充分

审查日期：2026-04-07

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/greedy/schedule_params.py, core/services/scheduler/schedule_input_builder.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 7
- 问题严重级别分布: 高 0 / 中 2 / 低 5
- 最新结论: ## 审查总结 经过三轮深度审查（引用链核实 → 接口设计与影响链 → 整体架构质量与完成判定），对算法层统一估算与派工重构 plan 做出以下结论： ### 总体评价：优秀，有条件通过 plan 在以下方面表现出色： 1. **引用准确性**：12 个核心文件中所有行号引用与实际代码高度吻合，9 条修订前提全部经代码验证成立 2. **任务设计严谨**：5 个任务的串行依赖关系与代码依赖一致，职责分离清晰 3. **约束条件自洽**：Python 3.8 兼容性、公开签名不变、30% 耗时阈值守门等约束完备且互不矛盾 4. **风控机制充分**：先写失败用例、耗时对照基线、"不做什么"清单、已知局限显式声明 5. **避让循环上界正确**：形式化证明了 `guard_limit = N_machine + N_operator + N_downtime + 1` 的数学可靠性 ### 需要修订的 2 个中等问题（建议实施前处理） 1. **`estimate_internal_slot` 缺少 `base_time` 参数**：当前设计依赖隐式前置条件 `prev_end >= base_time`，应增加参数或在入口做防御性 `max` 操作 2. **`schedule_optimizer.py` 中 `ready_date` 使用 `field="due_date"` 解析**：任务 4 步骤 4 遗漏了 optimizer 中 `ready_date` 的字段名修复，严格模式下会产生误导性错误消息 ### 5 个低等问题（可在实施中顺带处理） - `auto_assign.py` 效率读取现状的文档补充 - `_blocked` 返回值技术债的显式声明 - 本地搜索邻域去重在小规模场景的 shake 重置策略 - `sgs.py` 两条评分路径替换策略的显式标注 - 完成判定中 `downtime.py` 合理上界与固定硬上限的区分 ### 无高等问题 未发现会阻断实施或导致数据损坏的严重逻辑缺陷。plan 的设计意图正确、实施路径合理、边界处理到位。
- 下一步建议: 将 2 个中等问题纳入 plan 修订后即可开始执行任务 1
- 总体结论: 有条件通过

## 评审发现

### auto_assign.py 效率读取已使用 is not None 模式

- ID: F-docs-1
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 修订前提 7 说 scheduler.py:494 与 sgs.py:323 使用 or 1.0 隐式回退，但未提到 auto_assign.py:166-167 已经使用了 raw_eff is not None 模式。这不会影响实施（因为两处都将委托给新估算器），但会造成理解误差：读者可能以为三处都需要改，实际上 auto_assign 只需要删除外层 except Exception: eff = 1.0 即可。
- 建议:

  在修订前提中补充说明 auto_assign.py 当前效率读取已部分改善，仅外层异常捕获仍需消除。
- 证据:
  - `core/algorithms/greedy/auto_assign.py:163-175`
  - `core/algorithms/greedy/auto_assign.py`

### estimate_internal_slot 缺少 base_time 参数

- ID: F-javascript-2
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 中 estimate_internal_slot 的参数列表包含 prev_end（说明由调用方从 batch_progress.get(bid, base_time) 预计算后传入），但缺少 base_time。当前代码 scheduler.py:472 做 earliest = max(prev_end, base_time)，而 prev_end = batch_progress.get(bid, base_time) 在正常初始化下 >= base_time。但如果估算器被调用时 prev_end < base_time（例如 batch_progress 因外部逻辑异常写入了更早的时间），估算器会从一个早于起算时间的时刻开始排产。

  根因：plan 假设了 batch_progress.get(bid, base_time) >= base_time 这个不变式永远成立，但未在估算器接口中显式保证。

  影响范围：_schedule_internal 和 auto_assign 的所有调用路径。
- 建议:

  建议 estimate_internal_slot 的参数列表增加 base_time，或在文档中显式声明 prev_end 的前置条件 prev_end >= base_time，并在估算器入口添加 earliest = max(prev_end, base_time) 作为防御。

### optimizer 中 ready_date 解析使用了错误的字段标识

- ID: F-javascript-3
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  schedule_optimizer.py:335-341 的本地 _parse_date 始终使用 field='due_date' 调用 parse_optional_date，但在 367 行用于解析 ready_date：
  ready_date=_parse_date(getattr(b, 'ready_date', None))

  严格模式下如果 ready_date 格式不合法，抛出的 ValidationError 消息会说 '字段 due_date 格式不合法'，用户会误以为是 due_date 有问题。

  plan 任务 4 步骤 4 第 1 点只说 'dispatch_sgs() 与 schedule_optimizer.py 继续使用 parse_optional_date(..., field="due_date") 处理 due_date'，但未显式要求修复 optimizer 中 ready_date 的 field 名称。任务 4 步骤 4 第 2 点只针对 scheduler.py 的 ready_date/created_at 做了字段级边界包装，遗漏了 schedule_optimizer.py 中的同一问题。
- 建议:

  任务 4 步骤 4 应补充：schedule_optimizer.py 的 _parse_date 在解析 ready_date 时必须使用 field='ready_date'，不得复用 due_date 名义。可以改为使用两个分别具名的本地函数，或直接在 BatchForSort 构造处使用共享解析器加字段级 field 参数。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:335-341`
  - `core/services/scheduler/schedule_optimizer.py:367`
  - `core/services/scheduler/schedule_optimizer.py`

### _schedule_internal 的 _blocked 返回值在派工分支中从未使用

- ID: F-javascript-4
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  _schedule_internal 返回 (Optional[ScheduleResult], bool)，其中第二个 bool（_blocked）表示'是否因窗口截止而被阻断'。但在 sgs.py:431/436 和 batch_order.py:58/69 中，_blocked 均被忽略（以下划线前缀命名）。两条派工分支无论 _blocked 为 True 或 False 都执行相同逻辑：result 为 None 时一律 failed_count++ 并加入 blocked_batches。

  plan 的 InternalSlotEstimate 区分了 blocked_by_window 和 cutoff_exceeded 两个语义，但未说明重构后 _schedule_internal 的返回值是否还需要保留第二个 bool。如果保留，两条派工分支仍然忽略它；如果删除，需要改返回签名——但 plan 约束说'公开函数签名保持不变'。

  _schedule_external 也返回 (result, blocked)，两处都同样忽略了 blocked。
- 建议:

  建议在 plan 中明确说明：_schedule_internal 的返回签名 (Optional[ScheduleResult], bool) 本轮保持不变以遵守约束，但 _blocked 在两条派工分支中本就未使用，属于已知技术债。如后续要利用 blocked_by_window 做差异化处理（如仅因窗口截止时不计入 failed），可另开 plan。

### 本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽

- ID: F-本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 5 步骤 4 说 '接受更优解或执行 shake 后继续沿用同一个 seen_hashes，不重置已尝试顺序集合'。这意味着 shake/restart 产生的新起点如果与之前尝试过的某个邻域相同，会被跳过。在时间预算充裕、批次数量少（例如 < 10）时，排列空间有限，seen_hashes 可能快速覆盖大部分可能的邻域，导致后续迭代大量空转。

  当前代码（无去重）的行为是允许重复尝试，虽然浪费计算但保证搜索空间不会因去重而过早收敛。plan 引入去重后，在极端小规模场景下可能产生'有时间但无可用邻域'的退化。
- 建议:

  建议在 shake 阶段做轻量重置（如清空 seen_hashes 但保留当前 best），或在 seen_hashes.size 超过某个阈值时停止去重检查。这样既避免小规模场景的搜索空间耗尽，又在大规模场景享受去重收益。

### sgs.py 中 find_earliest_available_start 的两条路径替换策略可更显式

- ID: F-maintainability-6
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务 2 步骤 3 第 6 点说删除 find_earliest_available_start 导入，但仅通过“不可评分路径简化为 batch_progress.get(bid, base_time)”和“正常评分改用 estimate_internal_slot”解释了“不可评分”路径和“已有资源”路径。但实际上 find_earliest_available_start 在 sgs.py 中共被调用 8 次（310-312 行不可评分路径 3 次 + 317-319 行正常评分路径 3 次 + 导入 1 次 + 定义 1 次）。plan 应明确说明两条路径的替换策略：

  1. 不可评分路径（310-312）→ _build_unscorable_dispatch_key 中直接用 batch_progress.get(bid, base_time)
  2. 正常评分路径（317-319）→ estimate_internal_slot 的真实估算

  plan 已隐含了这两点，但可以更显式地标注‘317-319 行正常内部评分路径’也将被 estimate_internal_slot 替代，从而彻底消除 sgs.py 对 find_earliest_available_start 的依赖。
- 建议:

  任务 2 步骤 3 可补充一句：‘317-319 行的正常内部评分路径也将被 _score_internal_candidate 中的 estimate_internal_slot 调用替代’。

### 完成判定未区分 downtime.py 中已有合理上界与 scheduler/auto_assign 中的固定硬上限

- ID: F-maintainability-7
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 完成判定第 1 条说‘固定 200 次硬上限已删除’，但完成判定中未提及 downtime.py:49 中的另一个循环上界。find_earliest_available_start 中的 guard > (len(ordered) + 1) 是基于有序片段数的合理上界，与 plan 要求的方式一致，本身不是固定硬上限。但完成判定应注明只有 scheduler.py:513 和 auto_assign.py:185 的 guard < 200 是要删除的固定硬上限，downtime.py 中的上界已经是合理的、基于片段数的上界。
- 建议:

  完成判定第 1 条可补充‘注意：downtime.py:49 中 find_earliest_available_start 的 guard > (len(ordered) + 1) 已经是基于片段数的合理上界，不属于本轮要删除的固定硬上限’。

## 评审里程碑

### M1 · 第一轮：引用链行号与数据流核实

- 状态: 已完成
- 记录时间: 2026-04-07T10:48:01.236Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/greedy/schedule_params.py
- 摘要:

  逐一核实 plan 中所有引用的代码行号、函数签名、数据流描述与实际源码是否吻合。共检查了 scheduler.py、auto_assign.py、sgs.py、batch_order.py、downtime.py、date_parsers.py、evaluation.py、dispatch_rules.py、ortools_bottleneck.py、schedule_optimizer.py、schedule_optimizer_steps.py、schedule_params.py 共 12 个文件。

  **核实结论**：plan 中引用的行号区间与实际代码高度一致，所有修订前提（1-9）与代码实际行为匹配。以下为核实详情：

  1. `scheduler.py:469-543`（内部工序估算主体）✓ 与实际代码完全吻合
  2. `auto_assign.py:156-223`（自动分配避让循环）✓ 吻合
  3. `sgs.py:278-340`（近似评分族）✓ 吻合
  4. `sgs.py:18-24`（严格模式日期包装）✓ 吻合
  5. `sgs.py:82-104`（avg_proc_hours 初始化）✓ 吻合，`isinstance(exc, Exception)` 永真死条件确认存在于第 97 行
  6. `sgs.py:458-475`（运行期状态更新）✓ 吻合
  7. `scheduler.py:289-304`（seed 预热状态更新）✓ 吻合
  8. `scheduler.py:138-146`（批次排序输入消费日期字段）✓ 行号与实际偏差 ±2 行，属可接受范围
  9. `scheduler.py:228-237`（ready_date 下界静默回退）✓ 吻合
  10. `batch_order.py:90-106`（运行期状态更新）✓ 吻合
  11. `evaluation.py:38-58`、`dispatch_rules.py:25-28`、`ortools_bottleneck.py:23-42`（重复日期函数）✓ 全部确认存在四套重复实现
  12. `schedule_optimizer.py:335-357`（本地重复 _parse_datetime）✓ 确认与 date_parsers.py 完全重复
  13. `schedule_optimizer_steps.py:306-334`（build_order 在 dr 内层重复构造）✓ 确认 build_order 只依赖 (strat, params0)，在 dispatch_rules 循环内重复调用
  14. `schedule_optimizer.py:139-178`（本地搜索无邻域去重）✓ 确认仅有 cand_order==cur_order 的空操作兜底，无跨迭代去重

  **导入链补充发现**：scheduler.py 的 `_parse_date`/`_parse_datetime` 实际通过 `schedule_params.py` 间接导入 `date_parsers.py`（不是直接导入），plan 可以更明确地说明这条导入链。
- 结论:

  逐一核实 plan 中所有引用的代码行号、函数签名、数据流描述与实际源码是否吻合。共检查了 scheduler.py、auto_assign.py、sgs.py、batch_order.py、downtime.py、date_parsers.py、evaluation.py、dispatch_rules.py、ortools_bottleneck.py、schedule_optimizer.py、schedule_optimizer_steps.py、schedule_params.py 共 12 个文件。 **核实结论**：plan 中引用的行号区间与实际代码高度一致，所有修订前提（1-9）与代码实际行为匹配。以下为核实详情： 1. `scheduler.py:469-543`（内部工序估算主体）✓ 与实际代码完全吻合 2. `auto_assign.py:156-223`（自动分配避让循环）✓ 吻合 3. `sgs.py:278-340`（近似评分族）✓ 吻合 4. `sgs.py:18-24`（严格模式日期包装）✓ 吻合 5. `sgs.py:82-104`（avg_proc_hours 初始化）✓ 吻合，`isinstance(exc, Exception)` 永真死条件确认存在于第 97 行 6. `sgs.py:458-475`（运行期状态更新）✓ 吻合 7. `scheduler.py:289-304`（seed 预热状态更新）✓ 吻合 8. `scheduler.py:138-146`（批次排序输入消费日期字段）✓ 行号与实际偏差 ±2 行，属可接受范围 9. `scheduler.py:228-237`（ready_date 下界静默回退）✓ 吻合 10. `batch_order.py:90-106`（运行期状态更新）✓ 吻合 11. `evaluation.py:38-58`、`dispatch_rules.py:25-28`、`ortools_bottleneck.py:23-42`（重复日期函数）✓ 全部确认存在四套重复实现 12. `schedule_optimizer.py:335-357`（本地重复 _parse_datetime）✓ 确认与 date_parsers.py 完全重复 13. `schedule_optimizer_steps.py:306-334`（build_order 在 dr 内层重复构造）✓ 确认 build_order 只依赖 (strat, params0)，在 dispatch_rules 循环内重复调用 14. `schedule_optimizer.py:139-178`（本地搜索无邻域去重）✓ 确认仅有 cand_order==cur_order 的空操作兜底，无跨迭代去重 **导入链补充发现**：scheduler.py 的 `_parse_date`/`_parse_datetime` 实际通过 `schedule_params.py` 间接导入 `date_parsers.py`（不是直接导入），plan 可以更明确地说明这条导入链。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-543`
  - `core/algorithms/greedy/auto_assign.py:156-223`
  - `core/algorithms/greedy/dispatch/sgs.py:278-340`
  - `core/algorithms/greedy/dispatch/sgs.py:360-425`
  - `core/algorithms/greedy/downtime.py:20-77`
  - `core/algorithms/evaluation.py:38-58`
  - `core/algorithms/dispatch_rules.py:25-28`
  - `core/algorithms/ortools_bottleneck.py:23-42`
  - `core/services/scheduler/schedule_optimizer.py:343-357`
  - `core/services/scheduler/schedule_optimizer_steps.py:306-334`
- 问题:
  - [低] 文档: auto_assign.py 效率读取已使用 is not None 模式

### M2 · 第二轮：接口设计缺陷与遗漏的影响链审查

- 状态: 已完成
- 记录时间: 2026-04-07T10:51:01.033Z
- 摘要:

  审查 plan 中五个任务的接口设计、参数传递、影响链完整性和边界处理。重点验证了以下几个维度：

  ## 1. `estimate_internal_slot` 接口设计分析

  **参数完整性问题**：plan 设计的 `estimate_internal_slot` 参数列表包含 `prev_end` 但缺少 `base_time`。当前 `_schedule_internal()` 在第 472 行执行 `earliest = max(prev_end, base_time)` 做了一层防御。虽然 `batch_progress.get(bid, base_time)` 在正常初始化下 >= `base_time`，但这是一个隐式前置条件，估算器接口应当自带或显式声明。

  **`changeover_penalty` 归属合理性**：确认 `changeover_penalty` 不参与时间估算过程，只是评分时利用 `last_op_type_by_machine` 计算的额外信息。估算器统一返回这个值是干净的设计，调用方按需取用。

  **`total_hours` 语义清晰度**：plan 定义 `InternalSlotEstimate.total_hours` 为"效率折算后的实际排产时长"，对应 `total_hours_base / efficiency`。由于效率依赖开工时刻且会在避让循环中重算，`total_hours` 是循环结束时的最终值。这与当前 `_scaled_hours(earliest)` 的语义一致。

  ## 2. `_blocked` 返回值影响链

  验证了 `_schedule_internal` 返回的 `(result, blocked)` 在 sgs.py（431/436 行）和 batch_order.py（58/69 行）中均以 `_blocked` 命名被忽略。两条派工分支对 `result=None` 的处理完全相同（都是 `failed_count++` 加入 `blocked_batches`），不区分"资源不足"和"窗口截止"。plan 的 `InternalSlotEstimate` 区分了 `blocked_by_window` 和 `cutoff_exceeded`，但未说明如何映射回现有返回签名。

  ## 3. `schedule_optimizer.py` 的 `ready_date` 字段名错误

  确认 `schedule_optimizer.py:367` 使用 `_parse_date(getattr(b, "ready_date", None))` 解析 `ready_date`，但 `_parse_date` 内部固定使用 `field="due_date"`。plan 任务 4 步骤 4 只修复了 `scheduler.py` 中的 `ready_date`/`created_at` 边界包装，遗漏了 `schedule_optimizer.py` 中的同一问题。

  ## 4. 避让循环上界正确性证明

  通过形式化分析确认 plan 的 `guard_limit = N_machine + N_operator + N_downtime + 1` 上界是正确的：由于 `earliest` 在每次避让中严格单调递增，且每次推进至少越过一个片段的结束时间，而每个片段最多贡献一次推进（因为 `earliest` 一旦超过片段末尾就不再与其重叠），所以迭代次数严格受限于总片段数。

  ## 5. 优化器微优化正确性

  确认 `_run_multi_start` 的 `build_order(strat, params0)` 确实只依赖 `(strat, params0)`，不依赖 `dispatch_mode` 或 `dispatch_rule`，因此缓存设计正确。同时确认 `_build_order` 是纯函数（无副作用），缓存安全。

  本地搜索邻域去重方案在大规模场景下合理，但在小规模场景（批次 < 10）下可能因排列空间有限导致搜索空间过早耗尽。
- 结论:

  审查 plan 中五个任务的接口设计、参数传递、影响链完整性和边界处理。重点验证了以下几个维度： ## 1. `estimate_internal_slot` 接口设计分析 **参数完整性问题**：plan 设计的 `estimate_internal_slot` 参数列表包含 `prev_end` 但缺少 `base_time`。当前 `_schedule_internal()` 在第 472 行执行 `earliest = max(prev_end, base_time)` 做了一层防御。虽然 `batch_progress.get(bid, base_time)` 在正常初始化下 >= `base_time`，但这是一个隐式前置条件，估算器接口应当自带或显式声明。 **`changeover_penalty` 归属合理性**：确认 `changeover_penalty` 不参与时间估算过程，只是评分时利用 `last_op_type_by_machine` 计算的额外信息。估算器统一返回这个值是干净的设计，调用方按需取用。 **`total_hours` 语义清晰度**：plan 定义 `InternalSlotEstimate.total_hours` 为"效率折算后的实际排产时长"，对应 `total_hours_base / efficiency`。由于效率依赖开工时刻且会在避让循环中重算，`total_hours` 是循环结束时的最终值。这与当前 `_scaled_hours(earliest)` 的语义一致。 ## 2. `_blocked` 返回值影响链 验证了 `_schedule_internal` 返回的 `(result, blocked)` 在 sgs.py（431/436 行）和 batch_order.py（58/69 行）中均以 `_blocked` 命名被忽略。两条派工分支对 `result=None` 的处理完全相同（都是 `failed_count++` 加入 `blocked_batches`），不区分"资源不足"和"窗口截止"。plan 的 `InternalSlotEstimate` 区分了 `blocked_by_window` 和 `cutoff_exceeded`，但未说明如何映射回现有返回签名。 ## 3. `schedule_optimizer.py` 的 `ready_date` 字段名错误 确认 `schedule_optimizer.py:367` 使用 `_parse_date(getattr(b, "ready_date", None))` 解析 `ready_date`，但 `_parse_date` 内部固定使用 `field="due_date"`。plan 任务 4 步骤 4 只修复了 `scheduler.py` 中的 `ready_date`/`created_at` 边界包装，遗漏了 `schedule_optimizer.py` 中的同一问题。 ## 4. 避让循环上界正确性证明 通过形式化分析确认 plan 的 `guard_limit = N_machine + N_operator + N_downtime + 1` 上界是正确的：由于 `earliest` 在每次避让中严格单调递增，且每次推进至少越过一个片段的结束时间，而每个片段最多贡献一次推进（因为 `earliest` 一旦超过片段末尾就不再与其重叠），所以迭代次数严格受限于总片段数。 ## 5. 优化器微优化正确性 确认 `_run_multi_start` 的 `build_order(strat, params0)` 确实只依赖 `(strat, params0)`，不依赖 `dispatch_mode` 或 `dispatch_rule`，因此缓存设计正确。同时确认 `_build_order` 是纯函数（无副作用），缓存安全。 本地搜索邻域去重方案在大规模场景下合理，但在小规模场景（批次 < 10）下可能因排列空间有限导致搜索空间过早耗尽。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-562#_schedule_internal`
  - `core/services/scheduler/schedule_optimizer.py:359-370`
  - `core/services/scheduler/schedule_optimizer.py:335-341#_parse_date`
  - `core/algorithms/greedy/scheduler.py:226-236`
  - `core/algorithms/greedy/dispatch/sgs.py:424-506`
  - `core/algorithms/greedy/dispatch/batch_order.py:86-122`
- 问题:
  - [中] JavaScript: estimate_internal_slot 缺少 base_time 参数
  - [中] JavaScript: optimizer 中 ready_date 解析使用了错误的字段标识
  - [低] JavaScript: _schedule_internal 的 _blocked 返回值在派工分支中从未使用
  - [低] JavaScript: 本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽

### M3 · 第三轮：整体架构质量、约束完备性、测试策略与完成判定终审

- 状态: 已完成
- 记录时间: 2026-04-07T10:52:33.315Z
- 摘要:

  ## 整体架构质量评价

  ### 优点

  1. **任务依赖关系严谨**：1→2→3→4→5 的串行约束合理。任务 2 确实需要任务 1 产出的 `internal_slot.py`；任务 3 和 4 都修改 `scheduler.py`，不并行避免了冲突。执行顺序与代码依赖一致。

  2. **职责分离清晰**：三个新模块（`internal_slot.py`、`runtime_state.py`、`date_parsers.py` 的扩展）各有明确边界：估算器只估算不占资源、状态更新器只更新统计不评分、日期工具只做纯转换不做业务判断。这种分离使得每个模块可独立测试。

  3. **"不做什么"清单详尽**：plan 明确列出 11 项不做的事，包括不扩到 schedule_summary、不新增快速评分分支、不修复 CalendarEngine 层的 `or 1.0` 等。这有效防止范围蔓延。

  4. **约束条件自洽**：`bisect.insort` 不使用 `key=` 参数与 Python 3.8 兼容性要求一致（`key=` 在 3.10 才引入）。已验证 `(datetime, datetime)` 元组的自然排序满足需求。

  5. **30% 耗时阈值守门**：plan 在任务 2 步骤 6 设置了明确的性能退化检查点。如果真实估算替代近似估算后性能下降超过 30%，不会在本轮私自补快速路径，而是暂停向用户汇报。这是一个良好的风险控制机制。

  6. **已知局限显式声明**：plan 第 11 条"明确不做的事项"清晰说明了 SGS 评分阶段与正式排产的重复估算问题，以及两次自动分配可能选出不同对的原因。这种透明性有助于后续维护。

  ### 潜在风险

  1. **行为变化的回归验证**：`get_efficiency()` 抛异常时不再静默回退是一个行为变化。虽然 plan 认为当前实际不可触发（因为 CalendarEngine 已经 `or 1.0`），但如果 CalendarEngine 的其他代码路径能绕过 `or 1.0`，就会在生产环境暴露新错误。plan 的测试策略覆盖了这个场景（任务 1 步骤 1 第 4 点），但只是单元测试层面；建议在端到端测试中也确认。

  2. **`find_earliest_available_start` 的全面替换**：`sgs.py` 中的 `find_earliest_available_start` 在两条路径中使用（不可评分路径 310-312 行 + 正常评分路径 317-319 行）。plan 的导入清理说"彻底删除 find_earliest_available_start 导入"，这要求两条路径都必须在改造中完全消除对它的依赖。

  3. **严格模式日期错误消息**：除了已记录的 `schedule_optimizer.py` 中 `ready_date` 使用 `field="due_date"` 的问题外，`scheduler.py:138` 也用 `parse_optional_date(due_raw, field="due_date")` 处理 `due_date`——这个是正确的。但 `sgs.py:20-22` 的非严格模式分支也固定用 `field="due_date"` 调用 `parse_optional_date`，哪怕是正确的 `due_date` 字段，非严格模式下 `parse_optional_date` 还能抛出非 `ValidationError` 异常（如 `TypeError`），这些会被外层 `except Exception: return None` 吞掉——plan 的改造不影响这个行为，但值得知晓。

  ### 测试策略评价

  1. **先写失败用例再实现**的策略（每个任务步骤 1→2→3）是业界最佳实践，确保新代码必须通过预期断言。
  2. **耗时对照基线**的保留（任务 2 步骤 1 和步骤 6）提供了量化的性能回归检测。
  3. **回归测试清单完整**：每个任务都列出了受影响的现有回归测试。

  ### 完成判定充分性

  plan 的 9 条完成判定覆盖了：功能收口（1-3）、时间线有序（4）、运行期状态收口（5）、日期来源统一（6）、优化器重复消除（7）、性能阈值（8）、无新静默回退（9）。这是一个全面的 checklist。
- 结论:

  plan \u6574\u4f53\u8d28\u91cf\u4f18\u79c0\uff0c\u53ef\u4ee5\u6309\u5f53\u524d\u7248\u672c\u6267\u884c\uff0c\u5efa\u8bae\u5c06\u5ba1\u67e5\u53d1\u73b0\u7684 2 \u4e2a\u4e2d\u7b49\u95ee\u9898\u7eb3\u5165\u5b9e\u65bd\u524d\u4fee\u8ba2\u3002
- 问题:
  - [低] 可维护性: sgs.py 中 find_earliest_available_start 的两条路径替换策略可更显式
  - [低] 可维护性: 完成判定未区分 downtime.py 中已有合理上界与 scheduler/auto_assign 中的固定硬上限

## 最终结论

## 审查总结

经过三轮深度审查（引用链核实 → 接口设计与影响链 → 整体架构质量与完成判定），对算法层统一估算与派工重构 plan 做出以下结论：

### 总体评价：优秀，有条件通过

plan 在以下方面表现出色：
1. **引用准确性**：12 个核心文件中所有行号引用与实际代码高度吻合，9 条修订前提全部经代码验证成立
2. **任务设计严谨**：5 个任务的串行依赖关系与代码依赖一致，职责分离清晰
3. **约束条件自洽**：Python 3.8 兼容性、公开签名不变、30% 耗时阈值守门等约束完备且互不矛盾
4. **风控机制充分**：先写失败用例、耗时对照基线、"不做什么"清单、已知局限显式声明
5. **避让循环上界正确**：形式化证明了 `guard_limit = N_machine + N_operator + N_downtime + 1` 的数学可靠性

### 需要修订的 2 个中等问题（建议实施前处理）

1. **`estimate_internal_slot` 缺少 `base_time` 参数**：当前设计依赖隐式前置条件 `prev_end >= base_time`，应增加参数或在入口做防御性 `max` 操作
2. **`schedule_optimizer.py` 中 `ready_date` 使用 `field="due_date"` 解析**：任务 4 步骤 4 遗漏了 optimizer 中 `ready_date` 的字段名修复，严格模式下会产生误导性错误消息

### 5 个低等问题（可在实施中顺带处理）

- `auto_assign.py` 效率读取现状的文档补充
- `_blocked` 返回值技术债的显式声明
- 本地搜索邻域去重在小规模场景的 shake 重置策略
- `sgs.py` 两条评分路径替换策略的显式标注
- 完成判定中 `downtime.py` 合理上界与固定硬上限的区分

### 无高等问题

未发现会阻断实施或导致数据损坏的严重逻辑缺陷。plan 的设计意图正确、实施路径合理、边界处理到位。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnohpk71-pxhqox",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T10:53:02.921Z",
  "finalizedAt": "2026-04-07T10:53:02.921Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan深度审查",
    "date": "2026-04-07",
    "overview": "对 .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md 进行三轮深度审查"
  },
  "scope": {
    "markdown": "## 审查目标\n\n对算法层统一估算与派工重构 plan 进行深度审查，验证：\n1. plan 中引用的代码行号、函数签名、数据流是否与实际代码一致\n2. 任务拆分与依赖关系是否合理\n3. 实现方案是否优雅简洁、无过度兜底或静默回退\n4. 是否存在遗漏的影响链或潜在 BUG\n5. 约束条件与完成判定是否充分\n\n审查日期：2026-04-07"
  },
  "summary": {
    "latestConclusion": "## 审查总结\n\n经过三轮深度审查（引用链核实 → 接口设计与影响链 → 整体架构质量与完成判定），对算法层统一估算与派工重构 plan 做出以下结论：\n\n### 总体评价：优秀，有条件通过\n\nplan 在以下方面表现出色：\n1. **引用准确性**：12 个核心文件中所有行号引用与实际代码高度吻合，9 条修订前提全部经代码验证成立\n2. **任务设计严谨**：5 个任务的串行依赖关系与代码依赖一致，职责分离清晰\n3. **约束条件自洽**：Python 3.8 兼容性、公开签名不变、30% 耗时阈值守门等约束完备且互不矛盾\n4. **风控机制充分**：先写失败用例、耗时对照基线、\"不做什么\"清单、已知局限显式声明\n5. **避让循环上界正确**：形式化证明了 `guard_limit = N_machine + N_operator + N_downtime + 1` 的数学可靠性\n\n### 需要修订的 2 个中等问题（建议实施前处理）\n\n1. **`estimate_internal_slot` 缺少 `base_time` 参数**：当前设计依赖隐式前置条件 `prev_end >= base_time`，应增加参数或在入口做防御性 `max` 操作\n2. **`schedule_optimizer.py` 中 `ready_date` 使用 `field=\"due_date\"` 解析**：任务 4 步骤 4 遗漏了 optimizer 中 `ready_date` 的字段名修复，严格模式下会产生误导性错误消息\n\n### 5 个低等问题（可在实施中顺带处理）\n\n- `auto_assign.py` 效率读取现状的文档补充\n- `_blocked` 返回值技术债的显式声明\n- 本地搜索邻域去重在小规模场景的 shake 重置策略\n- `sgs.py` 两条评分路径替换策略的显式标注\n- 完成判定中 `downtime.py` 合理上界与固定硬上限的区分\n\n### 无高等问题\n\n未发现会阻断实施或导致数据损坏的严重逻辑缺陷。plan 的设计意图正确、实施路径合理、边界处理到位。",
    "recommendedNextAction": "将 2 个中等问题纳入 plan 修订后即可开始执行任务 1",
    "reviewedModules": [
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/algorithms/greedy/schedule_params.py",
      "core/services/scheduler/schedule_input_builder.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 7,
    "severity": {
      "high": 0,
      "medium": 2,
      "low": 5
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：引用链行号与数据流核实",
      "status": "completed",
      "recordedAt": "2026-04-07T10:48:01.236Z",
      "summaryMarkdown": "逐一核实 plan 中所有引用的代码行号、函数签名、数据流描述与实际源码是否吻合。共检查了 scheduler.py、auto_assign.py、sgs.py、batch_order.py、downtime.py、date_parsers.py、evaluation.py、dispatch_rules.py、ortools_bottleneck.py、schedule_optimizer.py、schedule_optimizer_steps.py、schedule_params.py 共 12 个文件。\n\n**核实结论**：plan 中引用的行号区间与实际代码高度一致，所有修订前提（1-9）与代码实际行为匹配。以下为核实详情：\n\n1. `scheduler.py:469-543`（内部工序估算主体）✓ 与实际代码完全吻合\n2. `auto_assign.py:156-223`（自动分配避让循环）✓ 吻合\n3. `sgs.py:278-340`（近似评分族）✓ 吻合\n4. `sgs.py:18-24`（严格模式日期包装）✓ 吻合\n5. `sgs.py:82-104`（avg_proc_hours 初始化）✓ 吻合，`isinstance(exc, Exception)` 永真死条件确认存在于第 97 行\n6. `sgs.py:458-475`（运行期状态更新）✓ 吻合\n7. `scheduler.py:289-304`（seed 预热状态更新）✓ 吻合\n8. `scheduler.py:138-146`（批次排序输入消费日期字段）✓ 行号与实际偏差 ±2 行，属可接受范围\n9. `scheduler.py:228-237`（ready_date 下界静默回退）✓ 吻合\n10. `batch_order.py:90-106`（运行期状态更新）✓ 吻合\n11. `evaluation.py:38-58`、`dispatch_rules.py:25-28`、`ortools_bottleneck.py:23-42`（重复日期函数）✓ 全部确认存在四套重复实现\n12. `schedule_optimizer.py:335-357`（本地重复 _parse_datetime）✓ 确认与 date_parsers.py 完全重复\n13. `schedule_optimizer_steps.py:306-334`（build_order 在 dr 内层重复构造）✓ 确认 build_order 只依赖 (strat, params0)，在 dispatch_rules 循环内重复调用\n14. `schedule_optimizer.py:139-178`（本地搜索无邻域去重）✓ 确认仅有 cand_order==cur_order 的空操作兜底，无跨迭代去重\n\n**导入链补充发现**：scheduler.py 的 `_parse_date`/`_parse_datetime` 实际通过 `schedule_params.py` 间接导入 `date_parsers.py`（不是直接导入），plan 可以更明确地说明这条导入链。",
      "conclusionMarkdown": "逐一核实 plan 中所有引用的代码行号、函数签名、数据流描述与实际源码是否吻合。共检查了 scheduler.py、auto_assign.py、sgs.py、batch_order.py、downtime.py、date_parsers.py、evaluation.py、dispatch_rules.py、ortools_bottleneck.py、schedule_optimizer.py、schedule_optimizer_steps.py、schedule_params.py 共 12 个文件。 **核实结论**：plan 中引用的行号区间与实际代码高度一致，所有修订前提（1-9）与代码实际行为匹配。以下为核实详情： 1. `scheduler.py:469-543`（内部工序估算主体）✓ 与实际代码完全吻合 2. `auto_assign.py:156-223`（自动分配避让循环）✓ 吻合 3. `sgs.py:278-340`（近似评分族）✓ 吻合 4. `sgs.py:18-24`（严格模式日期包装）✓ 吻合 5. `sgs.py:82-104`（avg_proc_hours 初始化）✓ 吻合，`isinstance(exc, Exception)` 永真死条件确认存在于第 97 行 6. `sgs.py:458-475`（运行期状态更新）✓ 吻合 7. `scheduler.py:289-304`（seed 预热状态更新）✓ 吻合 8. `scheduler.py:138-146`（批次排序输入消费日期字段）✓ 行号与实际偏差 ±2 行，属可接受范围 9. `scheduler.py:228-237`（ready_date 下界静默回退）✓ 吻合 10. `batch_order.py:90-106`（运行期状态更新）✓ 吻合 11. `evaluation.py:38-58`、`dispatch_rules.py:25-28`、`ortools_bottleneck.py:23-42`（重复日期函数）✓ 全部确认存在四套重复实现 12. `schedule_optimizer.py:335-357`（本地重复 _parse_datetime）✓ 确认与 date_parsers.py 完全重复 13. `schedule_optimizer_steps.py:306-334`（build_order 在 dr 内层重复构造）✓ 确认 build_order 只依赖 (strat, params0)，在 dispatch_rules 循环内重复调用 14. `schedule_optimizer.py:139-178`（本地搜索无邻域去重）✓ 确认仅有 cand_order==cur_order 的空操作兜底，无跨迭代去重 **导入链补充发现**：scheduler.py 的 `_parse_date`/`_parse_datetime` 实际通过 `schedule_params.py` 间接导入 `date_parsers.py`（不是直接导入），plan 可以更明确地说明这条导入链。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 543
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 156,
          "lineEnd": 223
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 278,
          "lineEnd": 340
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 360,
          "lineEnd": 425
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 77
        },
        {
          "path": "core/algorithms/evaluation.py",
          "lineStart": 38,
          "lineEnd": 58
        },
        {
          "path": "core/algorithms/dispatch_rules.py",
          "lineStart": 25,
          "lineEnd": 28
        },
        {
          "path": "core/algorithms/ortools_bottleneck.py",
          "lineStart": 23,
          "lineEnd": 42
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 343,
          "lineEnd": 357
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 306,
          "lineEnd": 334
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/greedy/schedule_params.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-docs-1"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：接口设计缺陷与遗漏的影响链审查",
      "status": "completed",
      "recordedAt": "2026-04-07T10:51:01.033Z",
      "summaryMarkdown": "审查 plan 中五个任务的接口设计、参数传递、影响链完整性和边界处理。重点验证了以下几个维度：\n\n## 1. `estimate_internal_slot` 接口设计分析\n\n**参数完整性问题**：plan 设计的 `estimate_internal_slot` 参数列表包含 `prev_end` 但缺少 `base_time`。当前 `_schedule_internal()` 在第 472 行执行 `earliest = max(prev_end, base_time)` 做了一层防御。虽然 `batch_progress.get(bid, base_time)` 在正常初始化下 >= `base_time`，但这是一个隐式前置条件，估算器接口应当自带或显式声明。\n\n**`changeover_penalty` 归属合理性**：确认 `changeover_penalty` 不参与时间估算过程，只是评分时利用 `last_op_type_by_machine` 计算的额外信息。估算器统一返回这个值是干净的设计，调用方按需取用。\n\n**`total_hours` 语义清晰度**：plan 定义 `InternalSlotEstimate.total_hours` 为\"效率折算后的实际排产时长\"，对应 `total_hours_base / efficiency`。由于效率依赖开工时刻且会在避让循环中重算，`total_hours` 是循环结束时的最终值。这与当前 `_scaled_hours(earliest)` 的语义一致。\n\n## 2. `_blocked` 返回值影响链\n\n验证了 `_schedule_internal` 返回的 `(result, blocked)` 在 sgs.py（431/436 行）和 batch_order.py（58/69 行）中均以 `_blocked` 命名被忽略。两条派工分支对 `result=None` 的处理完全相同（都是 `failed_count++` 加入 `blocked_batches`），不区分\"资源不足\"和\"窗口截止\"。plan 的 `InternalSlotEstimate` 区分了 `blocked_by_window` 和 `cutoff_exceeded`，但未说明如何映射回现有返回签名。\n\n## 3. `schedule_optimizer.py` 的 `ready_date` 字段名错误\n\n确认 `schedule_optimizer.py:367` 使用 `_parse_date(getattr(b, \"ready_date\", None))` 解析 `ready_date`，但 `_parse_date` 内部固定使用 `field=\"due_date\"`。plan 任务 4 步骤 4 只修复了 `scheduler.py` 中的 `ready_date`/`created_at` 边界包装，遗漏了 `schedule_optimizer.py` 中的同一问题。\n\n## 4. 避让循环上界正确性证明\n\n通过形式化分析确认 plan 的 `guard_limit = N_machine + N_operator + N_downtime + 1` 上界是正确的：由于 `earliest` 在每次避让中严格单调递增，且每次推进至少越过一个片段的结束时间，而每个片段最多贡献一次推进（因为 `earliest` 一旦超过片段末尾就不再与其重叠），所以迭代次数严格受限于总片段数。\n\n## 5. 优化器微优化正确性\n\n确认 `_run_multi_start` 的 `build_order(strat, params0)` 确实只依赖 `(strat, params0)`，不依赖 `dispatch_mode` 或 `dispatch_rule`，因此缓存设计正确。同时确认 `_build_order` 是纯函数（无副作用），缓存安全。\n\n本地搜索邻域去重方案在大规模场景下合理，但在小规模场景（批次 < 10）下可能因排列空间有限导致搜索空间过早耗尽。",
      "conclusionMarkdown": "审查 plan 中五个任务的接口设计、参数传递、影响链完整性和边界处理。重点验证了以下几个维度： ## 1. `estimate_internal_slot` 接口设计分析 **参数完整性问题**：plan 设计的 `estimate_internal_slot` 参数列表包含 `prev_end` 但缺少 `base_time`。当前 `_schedule_internal()` 在第 472 行执行 `earliest = max(prev_end, base_time)` 做了一层防御。虽然 `batch_progress.get(bid, base_time)` 在正常初始化下 >= `base_time`，但这是一个隐式前置条件，估算器接口应当自带或显式声明。 **`changeover_penalty` 归属合理性**：确认 `changeover_penalty` 不参与时间估算过程，只是评分时利用 `last_op_type_by_machine` 计算的额外信息。估算器统一返回这个值是干净的设计，调用方按需取用。 **`total_hours` 语义清晰度**：plan 定义 `InternalSlotEstimate.total_hours` 为\"效率折算后的实际排产时长\"，对应 `total_hours_base / efficiency`。由于效率依赖开工时刻且会在避让循环中重算，`total_hours` 是循环结束时的最终值。这与当前 `_scaled_hours(earliest)` 的语义一致。 ## 2. `_blocked` 返回值影响链 验证了 `_schedule_internal` 返回的 `(result, blocked)` 在 sgs.py（431/436 行）和 batch_order.py（58/69 行）中均以 `_blocked` 命名被忽略。两条派工分支对 `result=None` 的处理完全相同（都是 `failed_count++` 加入 `blocked_batches`），不区分\"资源不足\"和\"窗口截止\"。plan 的 `InternalSlotEstimate` 区分了 `blocked_by_window` 和 `cutoff_exceeded`，但未说明如何映射回现有返回签名。 ## 3. `schedule_optimizer.py` 的 `ready_date` 字段名错误 确认 `schedule_optimizer.py:367` 使用 `_parse_date(getattr(b, \"ready_date\", None))` 解析 `ready_date`，但 `_parse_date` 内部固定使用 `field=\"due_date\"`。plan 任务 4 步骤 4 只修复了 `scheduler.py` 中的 `ready_date`/`created_at` 边界包装，遗漏了 `schedule_optimizer.py` 中的同一问题。 ## 4. 避让循环上界正确性证明 通过形式化分析确认 plan 的 `guard_limit = N_machine + N_operator + N_downtime + 1` 上界是正确的：由于 `earliest` 在每次避让中严格单调递增，且每次推进至少越过一个片段的结束时间，而每个片段最多贡献一次推进（因为 `earliest` 一旦超过片段末尾就不再与其重叠），所以迭代次数严格受限于总片段数。 ## 5. 优化器微优化正确性 确认 `_run_multi_start` 的 `build_order(strat, params0)` 确实只依赖 `(strat, params0)`，不依赖 `dispatch_mode` 或 `dispatch_rule`，因此缓存设计正确。同时确认 `_build_order` 是纯函数（无副作用），缓存安全。 本地搜索邻域去重方案在大规模场景下合理，但在小规模场景（批次 < 10）下可能因排列空间有限导致搜索空间过早耗尽。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 562,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 370
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 341,
          "symbol": "_parse_date"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 226,
          "lineEnd": 236
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 424,
          "lineEnd": 506
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 86,
          "lineEnd": 122
        }
      ],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "findingIds": [
        "F-javascript-2",
        "F-javascript-3",
        "F-javascript-4",
        "F-本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：整体架构质量、约束完备性、测试策略与完成判定终审",
      "status": "completed",
      "recordedAt": "2026-04-07T10:52:33.315Z",
      "summaryMarkdown": "## 整体架构质量评价\n\n### 优点\n\n1. **任务依赖关系严谨**：1→2→3→4→5 的串行约束合理。任务 2 确实需要任务 1 产出的 `internal_slot.py`；任务 3 和 4 都修改 `scheduler.py`，不并行避免了冲突。执行顺序与代码依赖一致。\n\n2. **职责分离清晰**：三个新模块（`internal_slot.py`、`runtime_state.py`、`date_parsers.py` 的扩展）各有明确边界：估算器只估算不占资源、状态更新器只更新统计不评分、日期工具只做纯转换不做业务判断。这种分离使得每个模块可独立测试。\n\n3. **\"不做什么\"清单详尽**：plan 明确列出 11 项不做的事，包括不扩到 schedule_summary、不新增快速评分分支、不修复 CalendarEngine 层的 `or 1.0` 等。这有效防止范围蔓延。\n\n4. **约束条件自洽**：`bisect.insort` 不使用 `key=` 参数与 Python 3.8 兼容性要求一致（`key=` 在 3.10 才引入）。已验证 `(datetime, datetime)` 元组的自然排序满足需求。\n\n5. **30% 耗时阈值守门**：plan 在任务 2 步骤 6 设置了明确的性能退化检查点。如果真实估算替代近似估算后性能下降超过 30%，不会在本轮私自补快速路径，而是暂停向用户汇报。这是一个良好的风险控制机制。\n\n6. **已知局限显式声明**：plan 第 11 条\"明确不做的事项\"清晰说明了 SGS 评分阶段与正式排产的重复估算问题，以及两次自动分配可能选出不同对的原因。这种透明性有助于后续维护。\n\n### 潜在风险\n\n1. **行为变化的回归验证**：`get_efficiency()` 抛异常时不再静默回退是一个行为变化。虽然 plan 认为当前实际不可触发（因为 CalendarEngine 已经 `or 1.0`），但如果 CalendarEngine 的其他代码路径能绕过 `or 1.0`，就会在生产环境暴露新错误。plan 的测试策略覆盖了这个场景（任务 1 步骤 1 第 4 点），但只是单元测试层面；建议在端到端测试中也确认。\n\n2. **`find_earliest_available_start` 的全面替换**：`sgs.py` 中的 `find_earliest_available_start` 在两条路径中使用（不可评分路径 310-312 行 + 正常评分路径 317-319 行）。plan 的导入清理说\"彻底删除 find_earliest_available_start 导入\"，这要求两条路径都必须在改造中完全消除对它的依赖。\n\n3. **严格模式日期错误消息**：除了已记录的 `schedule_optimizer.py` 中 `ready_date` 使用 `field=\"due_date\"` 的问题外，`scheduler.py:138` 也用 `parse_optional_date(due_raw, field=\"due_date\")` 处理 `due_date`——这个是正确的。但 `sgs.py:20-22` 的非严格模式分支也固定用 `field=\"due_date\"` 调用 `parse_optional_date`，哪怕是正确的 `due_date` 字段，非严格模式下 `parse_optional_date` 还能抛出非 `ValidationError` 异常（如 `TypeError`），这些会被外层 `except Exception: return None` 吞掉——plan 的改造不影响这个行为，但值得知晓。\n\n### 测试策略评价\n\n1. **先写失败用例再实现**的策略（每个任务步骤 1→2→3）是业界最佳实践，确保新代码必须通过预期断言。\n2. **耗时对照基线**的保留（任务 2 步骤 1 和步骤 6）提供了量化的性能回归检测。\n3. **回归测试清单完整**：每个任务都列出了受影响的现有回归测试。\n\n### 完成判定充分性\n\nplan 的 9 条完成判定覆盖了：功能收口（1-3）、时间线有序（4）、运行期状态收口（5）、日期来源统一（6）、优化器重复消除（7）、性能阈值（8）、无新静默回退（9）。这是一个全面的 checklist。",
      "conclusionMarkdown": "plan \\u6574\\u4f53\\u8d28\\u91cf\\u4f18\\u79c0\\uff0c\\u53ef\\u4ee5\\u6309\\u5f53\\u524d\\u7248\\u672c\\u6267\\u884c\\uff0c\\u5efa\\u8bae\\u5c06\\u5ba1\\u67e5\\u53d1\\u73b0\\u7684 2 \\u4e2a\\u4e2d\\u7b49\\u95ee\\u9898\\u7eb3\\u5165\\u5b9e\\u65bd\\u524d\\u4fee\\u8ba2\\u3002",
      "evidence": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "findingIds": [
        "F-maintainability-6",
        "F-maintainability-7"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-docs-1",
      "severity": "low",
      "category": "docs",
      "title": "auto_assign.py 效率读取已使用 is not None 模式",
      "descriptionMarkdown": "plan 修订前提 7 说 scheduler.py:494 与 sgs.py:323 使用 or 1.0 隐式回退，但未提到 auto_assign.py:166-167 已经使用了 raw_eff is not None 模式。这不会影响实施（因为两处都将委托给新估算器），但会造成理解误差：读者可能以为三处都需要改，实际上 auto_assign 只需要删除外层 except Exception: eff = 1.0 即可。",
      "recommendationMarkdown": "在修订前提中补充说明 auto_assign.py 当前效率读取已部分改善，仅外层异常捕获仍需消除。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 175
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-javascript-2",
      "severity": "medium",
      "category": "javascript",
      "title": "estimate_internal_slot 缺少 base_time 参数",
      "descriptionMarkdown": "plan 中 estimate_internal_slot 的参数列表包含 prev_end（说明由调用方从 batch_progress.get(bid, base_time) 预计算后传入），但缺少 base_time。当前代码 scheduler.py:472 做 earliest = max(prev_end, base_time)，而 prev_end = batch_progress.get(bid, base_time) 在正常初始化下 >= base_time。但如果估算器被调用时 prev_end < base_time（例如 batch_progress 因外部逻辑异常写入了更早的时间），估算器会从一个早于起算时间的时刻开始排产。\n\n根因：plan 假设了 batch_progress.get(bid, base_time) >= base_time 这个不变式永远成立，但未在估算器接口中显式保证。\n\n影响范围：_schedule_internal 和 auto_assign 的所有调用路径。",
      "recommendationMarkdown": "建议 estimate_internal_slot 的参数列表增加 base_time，或在文档中显式声明 prev_end 的前置条件 prev_end >= base_time，并在估算器入口添加 earliest = max(prev_end, base_time) 作为防御。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-javascript-3",
      "severity": "medium",
      "category": "javascript",
      "title": "optimizer 中 ready_date 解析使用了错误的字段标识",
      "descriptionMarkdown": "schedule_optimizer.py:335-341 的本地 _parse_date 始终使用 field='due_date' 调用 parse_optional_date，但在 367 行用于解析 ready_date：\nready_date=_parse_date(getattr(b, 'ready_date', None))\n\n严格模式下如果 ready_date 格式不合法，抛出的 ValidationError 消息会说 '字段 due_date 格式不合法'，用户会误以为是 due_date 有问题。\n\nplan 任务 4 步骤 4 第 1 点只说 'dispatch_sgs() 与 schedule_optimizer.py 继续使用 parse_optional_date(..., field=\"due_date\") 处理 due_date'，但未显式要求修复 optimizer 中 ready_date 的 field 名称。任务 4 步骤 4 第 2 点只针对 scheduler.py 的 ready_date/created_at 做了字段级边界包装，遗漏了 schedule_optimizer.py 中的同一问题。",
      "recommendationMarkdown": "任务 4 步骤 4 应补充：schedule_optimizer.py 的 _parse_date 在解析 ready_date 时必须使用 field='ready_date'，不得复用 due_date 名义。可以改为使用两个分别具名的本地函数，或直接在 BatchForSort 构造处使用共享解析器加字段级 field 参数。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 341
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 367,
          "lineEnd": 367
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-javascript-4",
      "severity": "low",
      "category": "javascript",
      "title": "_schedule_internal 的 _blocked 返回值在派工分支中从未使用",
      "descriptionMarkdown": "_schedule_internal 返回 (Optional[ScheduleResult], bool)，其中第二个 bool（_blocked）表示'是否因窗口截止而被阻断'。但在 sgs.py:431/436 和 batch_order.py:58/69 中，_blocked 均被忽略（以下划线前缀命名）。两条派工分支无论 _blocked 为 True 或 False 都执行相同逻辑：result 为 None 时一律 failed_count++ 并加入 blocked_batches。\n\nplan 的 InternalSlotEstimate 区分了 blocked_by_window 和 cutoff_exceeded 两个语义，但未说明重构后 _schedule_internal 的返回值是否还需要保留第二个 bool。如果保留，两条派工分支仍然忽略它；如果删除，需要改返回签名——但 plan 约束说'公开函数签名保持不变'。\n\n_schedule_external 也返回 (result, blocked)，两处都同样忽略了 blocked。",
      "recommendationMarkdown": "建议在 plan 中明确说明：_schedule_internal 的返回签名 (Optional[ScheduleResult], bool) 本轮保持不变以遵守约束，但 _blocked 在两条派工分支中本就未使用，属于已知技术债。如后续要利用 blocked_by_window 做差异化处理（如仅因窗口截止时不计入 failed），可另开 plan。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽",
      "severity": "low",
      "category": "javascript",
      "title": "本地搜索邻域去重在小规模场景可能导致搜索空间过早耗尽",
      "descriptionMarkdown": "plan 任务 5 步骤 4 说 '接受更优解或执行 shake 后继续沿用同一个 seen_hashes，不重置已尝试顺序集合'。这意味着 shake/restart 产生的新起点如果与之前尝试过的某个邻域相同，会被跳过。在时间预算充裕、批次数量少（例如 < 10）时，排列空间有限，seen_hashes 可能快速覆盖大部分可能的邻域，导致后续迭代大量空转。\n\n当前代码（无去重）的行为是允许重复尝试，虽然浪费计算但保证搜索空间不会因去重而过早收敛。plan 引入去重后，在极端小规模场景下可能产生'有时间但无可用邻域'的退化。",
      "recommendationMarkdown": "建议在 shake 阶段做轻量重置（如清空 seen_hashes 但保留当前 best），或在 seen_hashes.size 超过某个阈值时停止去重检查。这样既避免小规模场景的搜索空间耗尽，又在大规模场景享受去重收益。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-6",
      "severity": "low",
      "category": "maintainability",
      "title": "sgs.py 中 find_earliest_available_start 的两条路径替换策略可更显式",
      "descriptionMarkdown": "plan 任务 2 步骤 3 第 6 点说删除 find_earliest_available_start 导入，但仅通过“不可评分路径简化为 batch_progress.get(bid, base_time)”和“正常评分改用 estimate_internal_slot”解释了“不可评分”路径和“已有资源”路径。但实际上 find_earliest_available_start 在 sgs.py 中共被调用 8 次（310-312 行不可评分路径 3 次 + 317-319 行正常评分路径 3 次 + 导入 1 次 + 定义 1 次）。plan 应明确说明两条路径的替换策略：\n\n1. 不可评分路径（310-312）→ _build_unscorable_dispatch_key 中直接用 batch_progress.get(bid, base_time)\n2. 正常评分路径（317-319）→ estimate_internal_slot 的真实估算\n\nplan 已隐含了这两点，但可以更显式地标注‘317-319 行正常内部评分路径’也将被 estimate_internal_slot 替代，从而彻底消除 sgs.py 对 find_earliest_available_start 的依赖。",
      "recommendationMarkdown": "任务 2 步骤 3 可补充一句：‘317-319 行的正常内部评分路径也将被 _score_internal_candidate 中的 estimate_internal_slot 调用替代’。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-7",
      "severity": "low",
      "category": "maintainability",
      "title": "完成判定未区分 downtime.py 中已有合理上界与 scheduler/auto_assign 中的固定硬上限",
      "descriptionMarkdown": "plan 完成判定第 1 条说‘固定 200 次硬上限已删除’，但完成判定中未提及 downtime.py:49 中的另一个循环上界。find_earliest_available_start 中的 guard > (len(ordered) + 1) 是基于有序片段数的合理上界，与 plan 要求的方式一致，本身不是固定硬上限。但完成判定应注明只有 scheduler.py:513 和 auto_assign.py:185 的 guard < 200 是要删除的固定硬上限，downtime.py 中的上界已经是合理的、基于片段数的上界。",
      "recommendationMarkdown": "完成判定第 1 条可补充‘注意：downtime.py:49 中 find_earliest_available_start 的 guard > (len(ordered) + 1) 已经是基于片段数的合理上界，不属于本轮要删除的固定硬上限’。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:93f2ece8a7869b366fa229e022128cfc5ea1fb5b9add00f18e869c9790814319",
    "generatedAt": "2026-04-07T10:53:02.921Z",
    "locale": "zh-CN"
  }
}
```
