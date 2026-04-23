# 算法层统一估算与派工重构plan与review一致性深度审查
- 日期: 2026-04-07
- 概述: 针对实施 plan 及其关联 review 文档做一致性、完整性、可执行性与证据链深度审查。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 算法层统一估算与派工重构plan与review一致性深度审查

- 日期：2026-04-07
- 范围：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其关联 `.limcode/review/算法层统一估算与派工重构plan深度审查.md`
- 方法：先审 plan 结构与任务设计，再核对 review 证据链与结论，最后交叉抽样源码验证两者是否严谨一致

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, .limcode/review/算法层统一估算与派工重构plan深度审查.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/date_parsers.py, core/services/common/strict_parse.py, core/services/scheduler/calendar_engine.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 2 / 低 1
- 最新结论: 结论分两层： 1. **当前 plan 本身可以进入实施**。它的任务分解、边界约束、测试覆盖与调用链假设都经抽样核实，整体简洁、克制，没有额外引入过度兜底，也没有把静默回退重新包装成“兼容”。 2. **当前 plan 与其顶部关联 review 不能再视为完全同步的双文档权威集**。原关联 review 至少有三处需要 follow-up： - 对已经写入当前 plan 的多项修订仍按“待补强”表述； - 对效率 `0.0` 问题的现实可触发性定性过重； - 日期元数据前后不一致。 因此，本轮最终建议是：**实施时以当前 plan + 本次一致性审查为准**；原关联 review 只应作为历史参考，除非后续另行同步修订或被新的 artifact 指针替代。
- 下一步建议: 若接下来进入实现阶段，直接按 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 与本次一致性审查执行；若先做文档治理，则优先处理原关联 review 的内容漂移与日期漂移，再视需要维护 plan 顶部 source artifact 指针。
- 总体结论: 需要后续跟进

## 评审发现

### 关联review与当前plan漂移

- ID: R1
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  原关联 review 仍把 F1/F2/F4/F5/F7/F8 表述为待补强或开放项，但这些内容已经写入当前 plan：`prev_end` 参数、显式 `guard_limit` 表达式、两处 `abort_after` 检查、`sgs.py` 导入清理、SGS 双重自动分配已知局限说明、零时长工序回归用例均已存在。继续把该 review 视为当前 plan 的直接解释来源，会制造重复修改与错误优先级。
- 建议:

  把当前这份一致性审查作为后续实施前的主参考；若未来需要维护 artifact 链，应更新或替代原关联 review，而不是继续沿用其“待补强”结论。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:221-245#任务1_步骤3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:326-333#任务2_步骤3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:193-199#任务1_步骤1`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:597#明确不做的事项`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:30-31#评审摘要`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:45-67#F1_F2`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:99-120#F4_F5`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:143-185#F7_F8`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`

### review日期前后不一致

- ID: R2
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  原关联 review 头部日期写为 `2026-04-07`，但正文“审查日期”写成 `2025-07-26`。这类时间漂移不会改变技术判断，却会削弱文档可信度，也会让后续读者误判审查相对 plan 版本的先后关系。
- 建议:

  若后续重整原 review，请先统一头部日期与正文日期，再处理内容级修订。
- 证据:
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:1-12#header_scope`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`

### 效率0.0问题在review中被过度定性

- ID: R3
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  原关联 review 把 `scheduler.py` / `sgs.py` 的 `or 1.0` 直接表述为“当前可触发的真实 BUG”。但抽样源码显示，`CalendarEngine.get_efficiency()` 已先用 `float(policy.efficiency or 1.0)` 把 `0.0` 屏蔽成 `1.0`，因此算法层当前实际上拿不到 `0.0`。更准确的说法应是：算法层保留了一个被引擎层掩盖的语义债；一旦引擎层未来改正 `0.0` 暴露语义，算法层就会立刻出现错误统计与错误耗时折算。当前 plan 在“修订前提 7”中的表述比原关联 review 更准确。
- 建议:

  若后续需要保留原关联 review，应把 F3 从“当前算法层可直接触发的真实 BUG”改写为“被引擎层遮蔽的风险点/语义债”，并显式说明当前不扩到 `calendar_engine.py`。
- 证据:
  - `core/services/scheduler/calendar_engine.py:221-222#get_efficiency`
  - `core/algorithms/greedy/scheduler.py:491-498#_scaled_hours`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327#dispatch_sgs`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:36-37#修订前提7`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:72-81#F3`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/services/common/strict_parse.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`

## 评审里程碑

### M1 · 第一轮：plan 与关联 review 文本一致性核对

- 状态: 已完成
- 记录时间: 2026-04-07T08:31:37.874Z
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, .limcode/review/算法层统一估算与派工重构plan深度审查.md
- 摘要:

  先只对目标文档本身做逐段对照，不先下实现层结论。

  ## 本轮核对结果

  1. **当前 plan 文本已经吸收了原 review 的大部分“待补强项”**：
     - `prev_end` 参数已写入任务 1 参数列表；
     - `guard_limit = len(machine_timeline.get(machine_id) or []) + len(operator_timeline.get(operator_id) or []) + len(downtime_segments) + 1` 已明确写出；
     - `abort_after` 的两处检查点已明确写出；
     - `sgs.py` 的 `parse_required_float` / `find_earliest_available_start` 导入清理已明确写出；
     - SGS 双重自动分配的已知局限已写入“明确不做的事项”；
     - 零时长工序边界回归也已写入测试步骤。

  2. **因此，原关联 review 的摘要、下一步建议、以及 F1/F2/F4/F5/F7/F8 的“开放/待补强”表述，已经落后于当前 plan 版本。** 如果继续把该 review 当成当前 plan 的直接实施依据，会误导后续工作把已经落地到文本里的修改再做一遍。

  3. **原关联 review 还有一个文档级瑕疵**：外层头部日期是 `2026-04-07`，但正文“审查日期”写成 `2025-07-26`，存在明显时间漂移。

  ## 阶段结论

  从文档一致性角度看，问题主要不在当前 plan，而在“plan 顶部 source artifact 仍指向一份已经与当前 plan 失同步的 review”。
- 结论:

  当前 plan 文本比关联 review 更新；关联 review 已出现版本漂移，不宜再直接作为当前 plan 的唯一解释来源。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:221-245#任务1_步骤3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:326-333#任务2_步骤3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:193-199#任务1_步骤1`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:597#明确不做的事项`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:1-31#评审摘要`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:45-67#F1_F2`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:99-120#F4_F5`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:143-185#F7_F8`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`
- 下一步建议:

  进入第二轮：抽样源码核实争议最大的技术表述，尤其是效率 0.0、日期解析边界、以及主调用链是否与当前 plan 仍一致。
- 问题:
  - [中] 文档: 关联review与当前plan漂移
  - [低] 文档: review日期前后不一致

### M2 · 第二轮：抽样源码核实关键技术表述

- 状态: 已完成
- 记录时间: 2026-04-07T08:32:22.152Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/date_parsers.py, core/services/common/strict_parse.py, core/services/scheduler/calendar_engine.py, .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, .limcode/review/算法层统一估算与派工重构plan深度审查.md
- 摘要:

  在不把范围重新拉回“实现审查”的前提下，只抽样核实最可能影响 plan/review 判断的争议点。

  ## 核实结果

  1. **主调用链与当前 plan 的总纲描述一致**：
     `ScheduleService._run_schedule_impl()` 先调用 `collect_schedule_run_input()`，再调用 `orchestrate_schedule_run()`；后者继续调用 `optimize_schedule()`；优化器内部再经 `_run_ortools_warmstart()` / `_run_multi_start()` / `_run_local_search()` 与 `_schedule_with_optional_strict_mode()` 落到 `GreedyScheduler.schedule()`。因此，plan 用这条链作为任务组织骨架是成立的。

  2. **任务 1 的关键细节与源码现状吻合**：
     - `auto_assign.py` 的 `prev_end` 确实在循环外提前计算；
     - `abort_after` 对应的早停语义确实分成“adjust_to_working_time 之后的初始早停”和“避让循环内早停”两处；
     - `scheduler.py` 现状仍是固定 `200` 次上限 + 三条时间线同时避让。
     这说明当前 plan 中对 `prev_end`、`guard_limit`、双检查点的写法是基于真实代码，而不是凭空扩写。

  3. **任务 4 的日期边界描述也成立**：
     - `parse_optional_date()` 在空值时返回 `None`，否则委托严格日期解析；
     - `date_parsers.parse_date()` 永不抛异常；
     - `schedule_optimizer._parse_datetime()` 与 `date_parsers.parse_datetime()` 的宽松格式顺序一致。
     因此，plan 只统一算法层纯日期函数、保留严格模式边界包装，是严谨且简洁的。

  4. **原关联 review 对效率 `0.0` 问题的定性比当前 plan 更激进，但当前 plan 更准确**：
     `scheduler.py` 和 `sgs.py` 的确都使用了 `or 1.0`；但 `CalendarEngine.get_efficiency()` 本身已经 `float(... or 1.0)`，会先把 `0.0` 屏蔽成 `1.0`。所以“算法层当前会直接吃到 `0.0` 并漏记计数器”的说法并不准确。更准确的表述应是：算法层现有写法存在被引擎层掩盖的语义债，若未来引擎层改正 `0.0` 暴露语义，算法层会立即出问题。当前 plan 在“修订前提 7”中正是这样表述的。

  ## 阶段结论

  当前 plan 的技术前提与抽样源码一致；原关联 review 的主要问题不是“方向错”，而是有一部分结论没有跟上 plan 最新文本，另有一处对效率问题的现实可触发性表述过重。
- 结论:

  从源码抽样结果看，当前 plan 的关键技术判断成立；原关联 review 对效率 0.0 问题的定性需要降温并改成“被引擎层掩盖的语义债”。
- 证据:
  - `core/services/scheduler/schedule_service.py:262-289#_run_schedule_impl`
  - `core/services/scheduler/schedule_orchestrator.py:103-128#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_optimizer.py:264-336#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:99-150#_schedule_with_optional_strict_mode_and_warmstart`
  - `core/services/scheduler/schedule_optimizer_steps.py:269-350#_run_multi_start`
  - `core/algorithms/greedy/scheduler.py:56-71#GreedyScheduler.schedule`
  - `core/algorithms/greedy/auto_assign.py:39-40#prev_end`
  - `core/algorithms/greedy/auto_assign.py:157-205#auto_assign_internal_resources`
  - `core/algorithms/greedy/scheduler.py:491-513#_scaled_hours`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327#dispatch_sgs`
  - `core/services/scheduler/calendar_engine.py:221-222#get_efficiency`
  - `core/services/common/strict_parse.py:99-102#parse_optional_date`
  - `core/algorithms/greedy/date_parsers.py:7-41#parse_date_parse_datetime`
  - `core/services/scheduler/schedule_optimizer.py:343-357#_parse_datetime`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:31-37#修订前提`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:72-81#F3`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/services/common/strict_parse.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`
- 下一步建议:

  进入第三轮：形成对“当前 plan 是否可以直接进入实施、原关联 review 是否应被替代/降级引用”的最终结论。
- 问题:
  - [中] 文档: 效率0.0问题在review中被过度定性

### M3 · 第三轮：最终判定与处置策略

- 状态: 已完成
- 记录时间: 2026-04-07T08:32:53.538Z
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, .limcode/review/算法层统一估算与派工重构plan深度审查.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/date_parsers.py, core/services/common/strict_parse.py, core/services/scheduler/calendar_engine.py
- 摘要:

  在前两轮基础上，分别对“当前 plan 能否直接进入实施”和“当前 plan + 关联 review 这对文档能否一起作为权威依据”做拆分判定。

  ## 最终判断

  ### 一、就当前 plan 本身

  **可以进入实施。**

  理由：
  1. 任务边界清楚，明确限制了不扩到 `schedule_summary.py`、`core/services/report/calculations.py`、`calendar_engine.py` 等非本轮范围；
  2. 串行顺序 `1 → 2 → 3 → 4 → 5` 合理，避免了 `scheduler.py` 等热点文件的并发改写；
  3. 关键约束写得足够细：保持公开签名不变、不新增第二条排产链、不引入新的静默回退、不把 `occupy_resource()` 下沉、不退回顺序链式近似；
  4. 测试策略不仅覆盖主路径，也覆盖了 `abort_after`、零时长工序、>200 碎片片段、效率异常这类边界；
  5. 从抽样源码看，plan 当前文字与真实调用链、真实数据流和真实边界语义是一致的。

  ### 二、就“当前 plan + 顶部关联 review”这对文档

  **还不能当成完全同步的双文档权威集。**

  根因不在 plan，而在关联 review：
  - 它把已经写入当前 plan 的多项修订仍写成“待补强”；
  - 它对效率 `0.0` 问题的现实可触发性表述过重；
  - 它还存在日期漂移。

  因此，若现在直接沿着 plan 顶部的 source artifact 指针去读原关联 review，读者会得到一份部分过时的解释层文档。

  ## 建议处置

  1. **实施层面**：后续若按当前 plan 开工，应以“当前 plan + 本次一致性审查”作为主参考，而不是继续按原关联 review 的“需补强项”逐条排优先级。
  2. **文档层面**：后续若要恢复 artifact 链的一致性，有两种做法：
     - 做法 A：直接修订原关联 review，使其与当前 plan 同步；
     - 做法 B：保留原关联 review 作为历史记录，用本次一致性审查作为新的上位说明。
  3. **本轮 review mode 限制下**：本次只产出 review 结论，不改 plan，也不回写原关联 review。
- 结论:

  当前 plan 可直接进入实施；但当前 plan 与其顶部关联 review 不再完全同步，应以后者降级为历史参考，并以本次一致性审查作为新的解释层依据。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:19-23#目标与总体做法`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:71-82#实施约束`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:193-199#测试步骤`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:30-31#评审摘要`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md:72-81#F3`
  - `core/services/scheduler/schedule_service.py:262-289#_run_schedule_impl`
  - `core/services/scheduler/schedule_orchestrator.py:103-128#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_optimizer.py:264-336#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:99-150#_schedule_with_optional_strict_mode_and_warmstart`
  - `core/algorithms/greedy/scheduler.py:56-71#GreedyScheduler.schedule`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `.limcode/review/算法层统一估算与派工重构plan深度审查.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/services/common/strict_parse.py`
  - `core/services/scheduler/calendar_engine.py`
- 下一步建议:

  结束本次审查并出最终结论：实施时以当前 plan + 本次一致性审查为准；若未来要修复 artifact 链，再单独更新原关联 review 或替换 source artifact 指针。

## 最终结论

结论分两层：

1. **当前 plan 本身可以进入实施**。它的任务分解、边界约束、测试覆盖与调用链假设都经抽样核实，整体简洁、克制，没有额外引入过度兜底，也没有把静默回退重新包装成“兼容”。
2. **当前 plan 与其顶部关联 review 不能再视为完全同步的双文档权威集**。原关联 review 至少有三处需要 follow-up：
   - 对已经写入当前 plan 的多项修订仍按“待补强”表述；
   - 对效率 `0.0` 问题的现实可触发性定性过重；
   - 日期元数据前后不一致。

因此，本轮最终建议是：**实施时以当前 plan + 本次一致性审查为准**；原关联 review 只应作为历史参考，除非后续另行同步修订或被新的 artifact 指针替代。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnoctbk0-u5fvuj",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T08:33:05.343Z",
  "finalizedAt": "2026-04-07T08:33:05.343Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "算法层统一估算与派工重构plan与review一致性深度审查",
    "date": "2026-04-07",
    "overview": "针对实施 plan 及其关联 review 文档做一致性、完整性、可执行性与证据链深度审查。"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构plan与review一致性深度审查\n\n- 日期：2026-04-07\n- 范围：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其关联 `.limcode/review/算法层统一估算与派工重构plan深度审查.md`\n- 方法：先审 plan 结构与任务设计，再核对 review 证据链与结论，最后交叉抽样源码验证两者是否严谨一致"
  },
  "summary": {
    "latestConclusion": "结论分两层：\n\n1. **当前 plan 本身可以进入实施**。它的任务分解、边界约束、测试覆盖与调用链假设都经抽样核实，整体简洁、克制，没有额外引入过度兜底，也没有把静默回退重新包装成“兼容”。\n2. **当前 plan 与其顶部关联 review 不能再视为完全同步的双文档权威集**。原关联 review 至少有三处需要 follow-up：\n   - 对已经写入当前 plan 的多项修订仍按“待补强”表述；\n   - 对效率 `0.0` 问题的现实可触发性定性过重；\n   - 日期元数据前后不一致。\n\n因此，本轮最终建议是：**实施时以当前 plan + 本次一致性审查为准**；原关联 review 只应作为历史参考，除非后续另行同步修订或被新的 artifact 指针替代。",
    "recommendedNextAction": "若接下来进入实现阶段，直接按 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 与本次一致性审查执行；若先做文档治理，则优先处理原关联 review 的内容漂移与日期漂移，再视需要维护 plan 顶部 source artifact 指针。",
    "reviewedModules": [
      ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
      ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/services/common/strict_parse.py",
      "core/services/scheduler/calendar_engine.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 2,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：plan 与关联 review 文本一致性核对",
      "status": "completed",
      "recordedAt": "2026-04-07T08:31:37.874Z",
      "summaryMarkdown": "先只对目标文档本身做逐段对照，不先下实现层结论。\n\n## 本轮核对结果\n\n1. **当前 plan 文本已经吸收了原 review 的大部分“待补强项”**：\n   - `prev_end` 参数已写入任务 1 参数列表；\n   - `guard_limit = len(machine_timeline.get(machine_id) or []) + len(operator_timeline.get(operator_id) or []) + len(downtime_segments) + 1` 已明确写出；\n   - `abort_after` 的两处检查点已明确写出；\n   - `sgs.py` 的 `parse_required_float` / `find_earliest_available_start` 导入清理已明确写出；\n   - SGS 双重自动分配的已知局限已写入“明确不做的事项”；\n   - 零时长工序边界回归也已写入测试步骤。\n\n2. **因此，原关联 review 的摘要、下一步建议、以及 F1/F2/F4/F5/F7/F8 的“开放/待补强”表述，已经落后于当前 plan 版本。** 如果继续把该 review 当成当前 plan 的直接实施依据，会误导后续工作把已经落地到文本里的修改再做一遍。\n\n3. **原关联 review 还有一个文档级瑕疵**：外层头部日期是 `2026-04-07`，但正文“审查日期”写成 `2025-07-26`，存在明显时间漂移。\n\n## 阶段结论\n\n从文档一致性角度看，问题主要不在当前 plan，而在“plan 顶部 source artifact 仍指向一份已经与当前 plan 失同步的 review”。",
      "conclusionMarkdown": "当前 plan 文本比关联 review 更新；关联 review 已出现版本漂移，不宜再直接作为当前 plan 的唯一解释来源。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 221,
          "lineEnd": 245,
          "symbol": "任务1_步骤3",
          "excerptHash": "plan-task1-details"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 326,
          "lineEnd": 333,
          "symbol": "任务2_步骤3",
          "excerptHash": "plan-task2-import-cleanup"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 193,
          "lineEnd": 199,
          "symbol": "任务1_步骤1",
          "excerptHash": "plan-zero-duration-test"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 597,
          "lineEnd": 597,
          "symbol": "明确不做的事项",
          "excerptHash": "plan-known-limitation"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 1,
          "lineEnd": 31,
          "symbol": "评审摘要",
          "excerptHash": "review-summary-stale"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 45,
          "lineEnd": 67,
          "symbol": "F1_F2",
          "excerptHash": "review-f1-f2"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 99,
          "lineEnd": 120,
          "symbol": "F4_F5",
          "excerptHash": "review-f4-f5"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 143,
          "lineEnd": 185,
          "symbol": "F7_F8",
          "excerptHash": "review-f7-f8"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
      ],
      "recommendedNextAction": "进入第二轮：抽样源码核实争议最大的技术表述，尤其是效率 0.0、日期解析边界、以及主调用链是否与当前 plan 仍一致。",
      "findingIds": [
        "R1",
        "R2"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：抽样源码核实关键技术表述",
      "status": "completed",
      "recordedAt": "2026-04-07T08:32:22.152Z",
      "summaryMarkdown": "在不把范围重新拉回“实现审查”的前提下，只抽样核实最可能影响 plan/review 判断的争议点。\n\n## 核实结果\n\n1. **主调用链与当前 plan 的总纲描述一致**：\n   `ScheduleService._run_schedule_impl()` 先调用 `collect_schedule_run_input()`，再调用 `orchestrate_schedule_run()`；后者继续调用 `optimize_schedule()`；优化器内部再经 `_run_ortools_warmstart()` / `_run_multi_start()` / `_run_local_search()` 与 `_schedule_with_optional_strict_mode()` 落到 `GreedyScheduler.schedule()`。因此，plan 用这条链作为任务组织骨架是成立的。\n\n2. **任务 1 的关键细节与源码现状吻合**：\n   - `auto_assign.py` 的 `prev_end` 确实在循环外提前计算；\n   - `abort_after` 对应的早停语义确实分成“adjust_to_working_time 之后的初始早停”和“避让循环内早停”两处；\n   - `scheduler.py` 现状仍是固定 `200` 次上限 + 三条时间线同时避让。\n   这说明当前 plan 中对 `prev_end`、`guard_limit`、双检查点的写法是基于真实代码，而不是凭空扩写。\n\n3. **任务 4 的日期边界描述也成立**：\n   - `parse_optional_date()` 在空值时返回 `None`，否则委托严格日期解析；\n   - `date_parsers.parse_date()` 永不抛异常；\n   - `schedule_optimizer._parse_datetime()` 与 `date_parsers.parse_datetime()` 的宽松格式顺序一致。\n   因此，plan 只统一算法层纯日期函数、保留严格模式边界包装，是严谨且简洁的。\n\n4. **原关联 review 对效率 `0.0` 问题的定性比当前 plan 更激进，但当前 plan 更准确**：\n   `scheduler.py` 和 `sgs.py` 的确都使用了 `or 1.0`；但 `CalendarEngine.get_efficiency()` 本身已经 `float(... or 1.0)`，会先把 `0.0` 屏蔽成 `1.0`。所以“算法层当前会直接吃到 `0.0` 并漏记计数器”的说法并不准确。更准确的表述应是：算法层现有写法存在被引擎层掩盖的语义债，若未来引擎层改正 `0.0` 暴露语义，算法层会立即出问题。当前 plan 在“修订前提 7”中正是这样表述的。\n\n## 阶段结论\n\n当前 plan 的技术前提与抽样源码一致；原关联 review 的主要问题不是“方向错”，而是有一部分结论没有跟上 plan 最新文本，另有一处对效率问题的现实可触发性表述过重。",
      "conclusionMarkdown": "从源码抽样结果看，当前 plan 的关键技术判断成立；原关联 review 对效率 0.0 问题的定性需要降温并改成“被引擎层掩盖的语义债”。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 262,
          "lineEnd": 289,
          "symbol": "_run_schedule_impl",
          "excerptHash": "schedule-service-chain"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 103,
          "lineEnd": 128,
          "symbol": "orchestrate_schedule_run",
          "excerptHash": "schedule-orchestrator-chain"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 264,
          "lineEnd": 336,
          "symbol": "optimize_schedule",
          "excerptHash": "optimize-schedule-chain"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 99,
          "lineEnd": 150,
          "symbol": "_schedule_with_optional_strict_mode_and_warmstart",
          "excerptHash": "optimizer-steps-chain"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 269,
          "lineEnd": 350,
          "symbol": "_run_multi_start",
          "excerptHash": "optimizer-multistart-chain"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 71,
          "symbol": "GreedyScheduler.schedule",
          "excerptHash": "greedy-schedule-signature"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 39,
          "lineEnd": 40,
          "symbol": "prev_end",
          "excerptHash": "auto-assign-prev-end"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 157,
          "lineEnd": 205,
          "symbol": "auto_assign_internal_resources",
          "excerptHash": "auto-assign-abort-after"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 513,
          "symbol": "_scaled_hours",
          "excerptHash": "scheduler-efficiency-guard"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327,
          "symbol": "dispatch_sgs",
          "excerptHash": "sgs-efficiency-guard"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py",
          "lineStart": 221,
          "lineEnd": 222,
          "symbol": "get_efficiency",
          "excerptHash": "calendar-efficiency-mask"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 99,
          "lineEnd": 102,
          "symbol": "parse_optional_date",
          "excerptHash": "strict-parse-optional-date"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py",
          "lineStart": 7,
          "lineEnd": 41,
          "symbol": "parse_date_parse_datetime",
          "excerptHash": "date-parsers"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 343,
          "lineEnd": 357,
          "symbol": "_parse_datetime",
          "excerptHash": "optimizer-parse-datetime"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 31,
          "lineEnd": 37,
          "symbol": "修订前提",
          "excerptHash": "plan-preconditions"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 72,
          "lineEnd": 81,
          "symbol": "F3",
          "excerptHash": "review-f3-overstated"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/services/common/strict_parse.py",
        "core/services/scheduler/calendar_engine.py",
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
      ],
      "recommendedNextAction": "进入第三轮：形成对“当前 plan 是否可以直接进入实施、原关联 review 是否应被替代/降级引用”的最终结论。",
      "findingIds": [
        "R3"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：最终判定与处置策略",
      "status": "completed",
      "recordedAt": "2026-04-07T08:32:53.538Z",
      "summaryMarkdown": "在前两轮基础上，分别对“当前 plan 能否直接进入实施”和“当前 plan + 关联 review 这对文档能否一起作为权威依据”做拆分判定。\n\n## 最终判断\n\n### 一、就当前 plan 本身\n\n**可以进入实施。**\n\n理由：\n1. 任务边界清楚，明确限制了不扩到 `schedule_summary.py`、`core/services/report/calculations.py`、`calendar_engine.py` 等非本轮范围；\n2. 串行顺序 `1 → 2 → 3 → 4 → 5` 合理，避免了 `scheduler.py` 等热点文件的并发改写；\n3. 关键约束写得足够细：保持公开签名不变、不新增第二条排产链、不引入新的静默回退、不把 `occupy_resource()` 下沉、不退回顺序链式近似；\n4. 测试策略不仅覆盖主路径，也覆盖了 `abort_after`、零时长工序、>200 碎片片段、效率异常这类边界；\n5. 从抽样源码看，plan 当前文字与真实调用链、真实数据流和真实边界语义是一致的。\n\n### 二、就“当前 plan + 顶部关联 review”这对文档\n\n**还不能当成完全同步的双文档权威集。**\n\n根因不在 plan，而在关联 review：\n- 它把已经写入当前 plan 的多项修订仍写成“待补强”；\n- 它对效率 `0.0` 问题的现实可触发性表述过重；\n- 它还存在日期漂移。\n\n因此，若现在直接沿着 plan 顶部的 source artifact 指针去读原关联 review，读者会得到一份部分过时的解释层文档。\n\n## 建议处置\n\n1. **实施层面**：后续若按当前 plan 开工，应以“当前 plan + 本次一致性审查”作为主参考，而不是继续按原关联 review 的“需补强项”逐条排优先级。\n2. **文档层面**：后续若要恢复 artifact 链的一致性，有两种做法：\n   - 做法 A：直接修订原关联 review，使其与当前 plan 同步；\n   - 做法 B：保留原关联 review 作为历史记录，用本次一致性审查作为新的上位说明。\n3. **本轮 review mode 限制下**：本次只产出 review 结论，不改 plan，也不回写原关联 review。",
      "conclusionMarkdown": "当前 plan 可直接进入实施；但当前 plan 与其顶部关联 review 不再完全同步，应以后者降级为历史参考，并以本次一致性审查作为新的解释层依据。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 19,
          "lineEnd": 23,
          "symbol": "目标与总体做法",
          "excerptHash": "plan-goal-scope"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 71,
          "lineEnd": 82,
          "symbol": "实施约束",
          "excerptHash": "plan-constraints"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 193,
          "lineEnd": 199,
          "symbol": "测试步骤",
          "excerptHash": "plan-test-coverage"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 30,
          "lineEnd": 31,
          "symbol": "评审摘要",
          "excerptHash": "review-outdated-summary"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 72,
          "lineEnd": 81,
          "symbol": "F3",
          "excerptHash": "review-f3-overstated"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 262,
          "lineEnd": 289,
          "symbol": "_run_schedule_impl",
          "excerptHash": "schedule-service-chain"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 103,
          "lineEnd": 128,
          "symbol": "orchestrate_schedule_run",
          "excerptHash": "schedule-orchestrator-chain"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 264,
          "lineEnd": 336,
          "symbol": "optimize_schedule",
          "excerptHash": "optimize-schedule-chain"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 99,
          "lineEnd": 150,
          "symbol": "_schedule_with_optional_strict_mode_and_warmstart",
          "excerptHash": "optimizer-steps-chain"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 71,
          "symbol": "GreedyScheduler.schedule",
          "excerptHash": "greedy-schedule-signature"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/services/common/strict_parse.py",
        "core/services/scheduler/calendar_engine.py"
      ],
      "recommendedNextAction": "结束本次审查并出最终结论：实施时以当前 plan + 本次一致性审查为准；若未来要修复 artifact 链，再单独更新原关联 review 或替换 source artifact 指针。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "R1",
      "severity": "medium",
      "category": "docs",
      "title": "关联review与当前plan漂移",
      "descriptionMarkdown": "原关联 review 仍把 F1/F2/F4/F5/F7/F8 表述为待补强或开放项，但这些内容已经写入当前 plan：`prev_end` 参数、显式 `guard_limit` 表达式、两处 `abort_after` 检查、`sgs.py` 导入清理、SGS 双重自动分配已知局限说明、零时长工序回归用例均已存在。继续把该 review 视为当前 plan 的直接解释来源，会制造重复修改与错误优先级。",
      "recommendationMarkdown": "把当前这份一致性审查作为后续实施前的主参考；若未来需要维护 artifact 链，应更新或替代原关联 review，而不是继续沿用其“待补强”结论。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 221,
          "lineEnd": 245,
          "symbol": "任务1_步骤3",
          "excerptHash": "plan-task1-details"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 326,
          "lineEnd": 333,
          "symbol": "任务2_步骤3",
          "excerptHash": "plan-task2-import-cleanup"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 193,
          "lineEnd": 199,
          "symbol": "任务1_步骤1",
          "excerptHash": "plan-zero-duration-test"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 597,
          "lineEnd": 597,
          "symbol": "明确不做的事项",
          "excerptHash": "plan-known-limitation"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 30,
          "lineEnd": 31,
          "symbol": "评审摘要",
          "excerptHash": "review-summary-stale"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 45,
          "lineEnd": 67,
          "symbol": "F1_F2",
          "excerptHash": "review-f1-f2"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 99,
          "lineEnd": 120,
          "symbol": "F4_F5",
          "excerptHash": "review-f4-f5"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 143,
          "lineEnd": 185,
          "symbol": "F7_F8",
          "excerptHash": "review-f7-f8"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2",
      "severity": "low",
      "category": "docs",
      "title": "review日期前后不一致",
      "descriptionMarkdown": "原关联 review 头部日期写为 `2026-04-07`，但正文“审查日期”写成 `2025-07-26`。这类时间漂移不会改变技术判断，却会削弱文档可信度，也会让后续读者误判审查相对 plan 版本的先后关系。",
      "recommendationMarkdown": "若后续重整原 review，请先统一头部日期与正文日期，再处理内容级修订。",
      "evidence": [
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 1,
          "lineEnd": 12,
          "symbol": "header_scope",
          "excerptHash": "review-date-drift"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3",
      "severity": "medium",
      "category": "docs",
      "title": "效率0.0问题在review中被过度定性",
      "descriptionMarkdown": "原关联 review 把 `scheduler.py` / `sgs.py` 的 `or 1.0` 直接表述为“当前可触发的真实 BUG”。但抽样源码显示，`CalendarEngine.get_efficiency()` 已先用 `float(policy.efficiency or 1.0)` 把 `0.0` 屏蔽成 `1.0`，因此算法层当前实际上拿不到 `0.0`。更准确的说法应是：算法层保留了一个被引擎层掩盖的语义债；一旦引擎层未来改正 `0.0` 暴露语义，算法层就会立刻出现错误统计与错误耗时折算。当前 plan 在“修订前提 7”中的表述比原关联 review 更准确。",
      "recommendationMarkdown": "若后续需要保留原关联 review，应把 F3 从“当前算法层可直接触发的真实 BUG”改写为“被引擎层遮蔽的风险点/语义债”，并显式说明当前不扩到 `calendar_engine.py`。",
      "evidence": [
        {
          "path": "core/services/scheduler/calendar_engine.py",
          "lineStart": 221,
          "lineEnd": 222,
          "symbol": "get_efficiency",
          "excerptHash": "calendar-efficiency-mask"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 498,
          "symbol": "_scaled_hours",
          "excerptHash": "scheduler-efficiency-guard"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327,
          "symbol": "dispatch_sgs",
          "excerptHash": "sgs-efficiency-guard"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 36,
          "lineEnd": 37,
          "symbol": "修订前提7",
          "excerptHash": "plan-efficiency-nuance"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md",
          "lineStart": 72,
          "lineEnd": 81,
          "symbol": "F3",
          "excerptHash": "review-f3-overstated"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": ".limcode/review/算法层统一估算与派工重构plan深度审查.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:5ad2580aeefbd932a125a72d60024b7af6defce3c535672a14d369565cacfe16",
    "generatedAt": "2026-04-07T08:33:05.343Z",
    "locale": "zh-CN"
  }
}
```
