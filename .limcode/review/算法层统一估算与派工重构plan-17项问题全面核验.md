# 算法层统一估算与派工重构plan-17项问题全面核验
- 日期: 2026-04-07
- 概述: 围绕既有17项问题，对plan目标可达成性、实现优雅性、静默回退清理完整性与剩余BUG风险做一次新的深度review。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构plan-17项问题全面核验

- 日期：2026-04-07
- 范围：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其关联算法实现、调用链、测试覆盖点
- 目标：逐项核实既有17项问题是否成立，检查plan是否足以达成目标，是否仍存在遗漏、逻辑缝隙、过度兜底或静默回退残留

## 审查准则
1. 结论必须回到真实代码、真实调用链、真实变量流。
2. 不只看单点函数，还要看上游入参约束、下游消费语义、测试可验证性。
3. 对高风险项优先核验其是否会直接破坏plan的核心承诺：统一估算、统一打分、显式失败、避免静默退化。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/services/scheduler/schedule_optimizer.py, core/services/common/strict_parse.py, core/algorithms/greedy/date_parsers.py, core/algorithms/sort_strategies.py, core/services/scheduler/calendar_engine.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/services/scheduler/resource_pool_builder.py, data/repositories/machine_downtime_repo.py, tests/conftest.py, .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, core/services/scheduler/schedule_optimizer_steps.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 21
- 问题严重级别分布: 高 5 / 中 8 / 低 8
- 最新结论: 结论：有条件通过。 这份 plan 的主框架、拆分方向与目标对齐关系已经通过再次核验：它确实有能力把统一内部工时估算、评分语义收口、日期字段边界收口与优化器去重/微优化落到真实调用链上，且整体设计仍然相对克制，没有引入新的并行路径、额外快速分支或新的广域兜底。 但在真正开始实现前，仍有五个高风险点必须先写回 plan 并锁定实现顺序，否则会出现“方向正确、落地时悄悄失真”的情况： 1. `schedule_optimizer.py` 的 `ready_date` 字段标签 BUG； 2. `dispatch_sgs()` 评分主干广域吞异常； 3. `probe_only` 探测双层吞异常； 4. `optimize_schedule()` 中 `created_at` strict 只能由当前轮 `keys` 决定，而现有构造顺序做不到； 5. 任务3对 direct-call `machine_downtimes` 的有序性假设会静默收窄公开入口兼容边界。 除此之外，还有三类中风险约束也应一并补入 plan 文本： - `estimate_internal_slot()` 的上界必须在每次调用入口按当前时间线状态计算； - `runtime_state` 共享后要避免“结果已写入、随后状态更新抛错”的部分提交； - 效率回归必须直接用替身日历验证算法层，不得穿过引擎层抄底。 因此，本轮 review 不支持“按当前文本直接开做”，但支持“先修正文案与边界说明，再按该 plan 实施”。修正后，这份方案仍是目前最可行、也最简洁的一条路线。
- 下一步建议: 先修改 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`，把五个高风险点与三类中风险实现约束明确写入；修订完成后再进入实现，不要按当前文本直接编码。
- 总体结论: 有条件通过

## 评审发现

### 主链引用关系与 plan 前提一致，任务1/4拆分方向成立。

- ID: F-主链引用关系与-plan-前提一致-任务1-4拆分方向成立
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### `schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 仍写死 `field="due_date"`，这是现存 BUG，不修会直接破坏字段级 strict 边界。

- ID: F-other-2
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### `scheduler.py` 内 `ready_date` 既在 `BatchForSort` 构造处消费，也在 `batch_progress` 初始化处消费；plan 文本已覆盖方向，但仍需把两处真实触点写得更显式。

- ID: F-other-3
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### `validate_internal_hours()` 允许零工时与当前实现兼容，但 `quantity=0` 的语义仍需测试锁定。

- ID: F-other-4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### 避让上界公式本身正确，风险在于实现时不能把它做成跨调用缓存。

- ID: F-避让上界公式本身正确-风险在于实现时不能把它做成跨调用缓存
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### ready_date 字段标签 BUG

- ID: R1-F05
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  `schedule_optimizer.py:335-341` 的 `_parse_date()` 在 strict 与 non-strict 两支里都写死了 `field="due_date"`，但 `line 367` 实际拿它解析 `ready_date`。这会把坏 `ready_date` 伪装成 `due_date` 报错，直接破坏任务4想建立的字段级边界。该问题不是推演风险，而是当前代码已存在的实际 BUG。
- 建议:

  任务4必须显式拆成 `_parse_due_date()` 与 `_parse_ready_date()`，并让坏 `ready_date` 只以 `field="ready_date"` 抛错。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:335-367#optimize_schedule`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### scheduler.py 的 ready_date 触点需写实到两处

- ID: R1-F04
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  `GreedyScheduler.schedule()` 内 `ready_date` 不是只在一个地方消费。`line 145` 会把它放进 `BatchForSort`，`line 228-237` 又会把它转成 `batch_progress` 下界。plan 目前已经表达出“scheduler.py 中 ready_date 要做 strict/non-strict 收口、且不再对日历异常静默回退”的方向，但如果实施者只盯住排序构造处，就会遗漏 `batch_progress` 初始化处，造成同一字段在同一文件内仍有两套边界语义。
- 建议:

  在任务4步骤4里把 `scheduler.py:145` 与 `scheduler.py:228-237` 两个触点分别列出，避免只改一半。
- 证据:
  - `core/algorithms/greedy/scheduler.py:138-146#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:228-237#GreedyScheduler.schedule`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### 避让上界必须按调用时状态计算

- ID: R1-F02
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  再次核对 `scheduler.py:510-535` 与 `auto_assign.py:183-206` 可知，plan 提出的上界公式 `N_machine + N_operator + N_downtime + 1` 是成立的，核心目的正是取代固定 `200` 次上限。真正需要防止的不是公式失效，而是实现时把该上界缓存到调用时之外：`machine_timeline` 与 `operator_timeline` 会在排产过程中增长，所以只能在 `estimate_internal_slot()` 每次进入时按当时看到的片段数计算。该项更像实现约束，而不是 plan 架构性错误。
- 建议:

  把任务1中的上界说明改写成“由 `estimate_internal_slot()` 在每次调用入口按当前时间线长度计算”，避免被实现成预缓存常量。
- 证据:
  - `core/algorithms/greedy/scheduler.py:510-535#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:183-206#auto_assign_internal_resources`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### quantity=0 的零工时语义仍需测试锁定

- ID: R1-F01
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  当前 `_schedule_internal()` 与 `auto_assign_internal_resources()` 都允许 `setup_hours + unit_hours * quantity == 0` 通过，这与 plan 想保留的零时长工序兼容；但 `quantity=0, unit_hours>0` 与 `setup_hours=0, unit_hours=0` 在业务含义上并不相同。若不加测试，后续实现者可能在统一入口里无意收紧或放宽这一边界。
- 建议:

  在任务1测试中单列 `quantity=0, unit_hours>0` 场景，明确它是兼容性保留还是应视作坏数据。
- 证据:
  - `core/algorithms/greedy/scheduler.py:476-488#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:102-112#auto_assign_internal_resources`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`

### 评分主干广域吞异常

- ID: R2-F04
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `dispatch_sgs()` 当前在候选评分主循环外层保留了大范围 `except Exception`，见 `sgs.py:360-418`。这会把 `AttributeError`、`KeyError`、`NameError` 乃至接口契约违背都压扁成“最差但可比较”的 key，继续参与排序。由于 plan 的核心承诺之一就是把意外程序错误与业务不可估算彻底分离，这一类异常吞没必须在实施前被明确拔掉，否则任务2虽然做了拆分，语义上仍没有真正完成。
- 建议:

  拆分后的 `_score_internal_candidate()`、`_score_external_candidate()` 与候选循环主干都不应再保留这类广域异常降级；对外只允许五类明确业务不可估算原因生成降级 key。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:360-418#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### probe_only 探测仍吞程序错误

- ID: R3-F02
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `sgs.py:230-263` 的 `probe_only=True` 自动分配探测存在双层 `except Exception`：内层处理返回值解构，外层包住整个自动分配调用。结果是探测返回形状错误、自动分配内部异常、调用契约错误都会被等价折叠成“缺资源且无法自动分配”。这与任务2想建立的显式失败语义直接冲突，且影响面比一般提示性问题更大，因为它会静默改变候选优先级。
- 建议:

  把两层 `except Exception` 全部删掉，只保留 `chosen is None` 的正常分支；同时补一条回归，断言探测返回坏形状或抛异常时会直接暴露，而不是转成降级 key。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:230-263#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### seed 最近状态需要原子绑定更新

- ID: R1-F03
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  seed 预热与正式派工的最近状态语义并不相同。`scheduler.py:299-304` 中 `last_end_by_machine` 与 `last_op_type_by_machine` 是绑在同一个“更晚 end_time”条件上的；而 `batch_order.py:95-106` 与 `sgs.py:463-475` 则是 `last_end_by_machine` 条件覆盖、`last_op_type_by_machine` 非空即直接覆盖。plan 已识别这两种模式，但共享函数设计若只做布尔开关、没有保证 seed 分支里的原子绑定，就会把 seed 语义做坏。
- 建议:

  `runtime_state.py` 里 seed 模式要么单独函数实现，要么保证 `last_end_by_machine` 与 `last_op_type_by_machine` 在同一条件分支里同时更新。
- 证据:
  - `core/algorithms/greedy/scheduler.py:299-304#GreedyScheduler.schedule`
  - `core/algorithms/greedy/dispatch/batch_order.py:95-106#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/sgs.py:463-475#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 有序时间线前提会收窄 direct-call 停机输入边界

- ID: N2-F01
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  任务3计划把 `find_overlap_shift_end()` 与 `find_earliest_available_start()` 建立在“输入片段已经有序”的前提上，并明确写到 `machine_downtimes` 继续依赖 `resource_pool_builder.py` 的排序保证。服务主链这一点确实成立：`MachineDowntimeRepository.list_active_after()` 通过 `ORDER BY start_time ASC, id ASC` 返回数据，`resource_pool_builder.py` 只是顺序装入列表。但 `GreedyScheduler.schedule()` 是公开算法入口，签名直接允许外部调用方传入 `machine_downtimes` 原始字典。当前代码即使面对无序片段也能工作，因为 `find_overlap_shift_end()` 全量扫描、`find_earliest_available_start()` 还会自行 `sorted(...)`。如果按 plan 直接移除这些兜底而不在公开入口做一次归一化，就会对 direct-call 形成静默兼容性收窄：无序停机片段可能被早停逻辑漏检，直接排进停机窗口。
- 建议:

  不要只依赖服务层排序保证。更稳妥的做法是在 `GreedyScheduler.schedule()` 或新估算器入口对外部传入的 `machine_downtimes[mid]` 做一次轻量标准化，或把“公开入口要求有序停机片段”明文写进 plan 与回归。
- 证据:
  - `core/algorithms/greedy/scheduler.py:56-64#GreedyScheduler.schedule`
  - `core/algorithms/greedy/downtime.py:31-77#find_earliest_available_start`
  - `core/services/scheduler/resource_pool_builder.py:154-160#load_machine_downtimes`
  - `core/services/scheduler/resource_pool_builder.py:301-307#extend_downtime_map_for_resource_pool`
  - `data/repositories/machine_downtime_repo.py:43-55#MachineDowntimeRepository.list_active_after`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:372-379#任务 3`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 去掉状态更新吞异常后存在部分提交风险

- ID: N2-F02
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  当前 `batch_order.py` 与 `sgs.py` 都是在 `result` 已经 append、`batch_progress` 已推进、`scheduled_count` 已累加之后，才做忙时与最近状态更新；只是靠内层 `try/except` 把这些更新异常吃掉了，所以不会触发外层失败分支。一旦按 plan 去掉内层吞异常、改成共享 `runtime_state.py` 小函数，若该小函数抛异常，外层 `except` 会把同一工序再次计入失败并阻断批次，而先前写进 `results` 的成功结果却不会回滚，形成“已成功又失败”的部分提交状态。
- 建议:

  共享状态更新要么放到“提交结果”之前执行，要么做成对当前已守卫输入完全无异常的纯字典更新，避免仅靠删除 `try/except` 却留下部分提交。
- 证据:
  - `core/algorithms/greedy/dispatch/batch_order.py:58-106#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/sgs.py:453-475#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:489-504#dispatch_sgs`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:381-390#任务 3`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 删除 candidates[0] 前要消灭静默不返回路径

- ID: R2-F01
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `sgs.py:424-425` 当前的 `best_pair = candidates[0]` 的确是死代码，但它实际上承担了最后一道“所有候选都没产出 key”时的兜底。plan 的删除方向是对的，不过如果拆分后的 `_score_internal_candidate()` / `_score_external_candidate()` 仍保留“既不返回 key 也不抛异常”的路径，删除这行后就会把逻辑问题从静默劣化变成 `best_pair is None` 的运行时故障。
- 建议:

  删除 `candidates[0]` 之前，先用显式返回类型和回归用例锁死：每个评分分支不是返回正常 key，就是返回明确的业务不可估算 key，剩下的都直接抛异常。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:420-425#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### find_earliest_available_start 是否删除需明说

- ID: R2-F06
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  当前 `find_earliest_available_start()` 只被 `sgs.py` 的内部评分近似路径使用。plan 的任务2完成后，这条路径原则上应消失；如果函数随后仍保留，就连同其中的 `except Exception: dur = 0.0` 一起保留了一个已知静默回退残留。它不是当前主阻断，但需要在实施收尾时明确说明“已删除”还是“作为范围外遗留保留”。
- 建议:

  任务2完成后立刻复核此函数的引用；若无引用，直接删掉；若保留，需在完成判定中把它列为范围外残留。
- 证据:
  - `core/algorithms/greedy/downtime.py:31-41#find_earliest_available_start`
  - `core/algorithms/greedy/dispatch/sgs.py:15#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:310-319#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### created_at strict 启用时序错误

- ID: R3-F04
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  `optimize_schedule()` 当前在 `line 359-370` 先构造 `batch_for_sort`，随后才在 `line 392-401` 得到 `valid_strategies` 与 `keys`。但任务4要求 `created_at` 的 strict 只在当前轮次 `keys` 真正包含 `fifo` 时启用。也就是说，plan 的目标语义是正确的，但现有代码执行顺序与目标语义相互矛盾：如果不先调整顺序，就根本无法按 `keys` 决定 `created_at` 是否严格校验。
- 建议:

  把 `valid_strategies` / `keys` 的确定提前到 `batch_for_sort` 构造之前，或把 `created_at` 的 strict 解析延迟到已知 `keys` 之后；就当前结构而言，前移顺序是更简洁的修法。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:359-401#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 效率测试必须绕过引擎层抄底

- ID: R2-F07
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  算法层当前有三处效率读取：`scheduler.py:494`、`auto_assign.py:166-169`、`sgs.py:323-327`。计划要清掉算法层的 `or 1.0` 与外层吞异常，但 `CalendarEngine.get_efficiency()` 自身仍在 `line 221-222` 做 `or 1.0`。因此，如果测试不是直接注入替身日历，而是穿过真实引擎层，就无法证明算法层的清理是否生效，容易得到“测试绿了但目标没真正达成”的假结论。
- 建议:

  保留 plan 里的替身日历做法，并把“不得穿过 `CalendarEngine` 验证 0.0 效率”写得更硬一些，避免测试实现跑偏。
- 证据:
  - `core/algorithms/greedy/scheduler.py:491-496#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327#dispatch_sgs`
  - `core/algorithms/greedy/auto_assign.py:163-169#auto_assign_internal_resources`
  - `core/services/scheduler/calendar_engine.py:221-222#CalendarEngine.get_efficiency`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 局部搜索去重必须保持迭代推进顺序

- ID: R3-F03
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  当前 `_run_local_search()` 在 `while` 体一开始先做 `it += 1`，然后才会构造邻域。plan 要加入 `seen_hashes` 去重，如果把去重判断放到 `it += 1` 之前，就会在“所有邻域都重复”的小规模场景里留下无限循环风险。现有代码已经给出了正确顺序，plan 只需要明确保持，不需要另造复杂终止机制。
- 建议:

  在任务5步骤4里明确写出：`it += 1` 必须先于去重判断执行；重复邻域只是不计入 `attempts`，不是不计入迭代。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:135-140#_run_local_search`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:512-518#任务 5`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### build_order 重复构造已被准确识别

- ID: R1-F06
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  `_run_multi_start()` 里 `build_order(strat, params0)` 当前确实位于 `dispatch_rule` 内层循环，见 `schedule_optimizer_steps.py:331-334`。而排序结果只取决于 `strategy` 与 `params0`，与 `dispatch_mode` / `dispatch_rule` 无关，所以 plan 用 `(strategy.value, tuple(sorted(params0.items())))` 做缓存是正确且简洁的，不会引入额外语义分叉。
- 建议:

  该项无须额外升级，只要照 plan 方案做即可。
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:300-334#_run_multi_start`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:504-510#任务 5`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### strict_mode 冗余判断应顺手清掉

- ID: R3-F01
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  `sgs.py:96-99` 中 `except Exception as exc:` 之后又写 `if strict_mode and isinstance(exc, Exception): raise`，其中 `isinstance(exc, Exception)` 永远为真。这不是结构性问题，但会在重构时制造噪音，建议顺手删成 `if strict_mode: raise`。
- 建议:

  改造 `avg_proc_hours` 初始化段时一并清理，不要把冗余判断带入新代码。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:96-99#dispatch_sgs`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

## 评审里程碑

### M1 · 第一组核验：服务主链、统一估算入口与日期边界

- 状态: 已完成
- 记录时间: 2026-04-07T15:05:14.244Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/services/scheduler/schedule_optimizer.py, core/services/common/strict_parse.py, core/algorithms/greedy/date_parsers.py, core/algorithms/sort_strategies.py, core/services/scheduler/calendar_engine.py
- 摘要:

  本轮先沿 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 主链核对 plan 的任务1与任务4，重点检查三类问题：

  1. 统一内部工时入口是否会收窄 direct-call 原始输入边界；
  2. `ready_date` / `created_at` 的 strict 与 non-strict 边界是否真的落在实际消费点；
  3. 优化器与调度器两侧的日期解析标签、调用顺序、异常语义是否一致。

  结论：plan 的大方向仍然正确，任务1与任务4确实能达成“统一估算 + 单一日期事实源”的目标，但现有文本里对 `ready_date` 的两处真实消费点写得还不够落地，`schedule_optimizer.py` 的 `ready_date` 字段标签 BUG 则是实打实的高风险现存问题。与此同时，关于避让上界的讨论里，核心风险不在公式本身，而在实现时是否按“每次调用时的当前时间线状态”取值。
- 结论:

  任务1与任务4可以达成目标，但必须先补齐 `ready_date` 的真实落点说明，并修掉优化器中的字段标签 BUG。原先被归为高严重度的“避让上界”问题，经再次核对，更准确地说是实现约束而不是 plan 结构性缺陷：公式本身成立，关键在于不得把上界预缓存到调用时之外。
- 证据:
  - `core/services/scheduler/schedule_service.py:262-281#ScheduleService._run_schedule_impl`
  - `core/services/scheduler/schedule_input_collector.py:387-421#collect_schedule_run_input`
  - `core/services/scheduler/schedule_orchestrator.py:113-128#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_input_builder.py:128-145#_build_algo_operations_outcome`
  - `core/algorithms/greedy/scheduler.py:138-146#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:228-237#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:476-488#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:102-112#auto_assign_internal_resources`
  - `core/services/scheduler/schedule_optimizer.py:335-401#optimize_schedule`
  - `core/services/common/strict_parse.py:85-102#parse_optional_date`
  - `core/algorithms/greedy/date_parsers.py:7-41#parse_date`
  - `core/algorithms/sort_strategies.py:117-125#FIFOStrategy.sort`
  - `core/services/scheduler/calendar_engine.py:221-222#CalendarEngine.get_efficiency`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/sort_strategies.py`
  - `core/services/scheduler/calendar_engine.py`
- 下一步建议:

  继续下钻任务2与任务3，重点核对 `dispatch_sgs()` 的异常语义、`runtime_state` 收口后的状态一致性，以及有序时间线假设是否会收窄 direct-call 边界。
- 问题:
  - [低] 其他: 主链引用关系与 plan 前提一致，任务1/4拆分方向成立。
  - [低] 其他: `schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 仍写死 `field="due_date"`，这是现存 BUG，不修会直接破坏字段级 strict 边界。
  - [低] 其他: `scheduler.py` 内 `ready_date` 既在 `BatchForSort` 构造处消费，也在 `batch_progress` 初始化处消费；plan 文本已覆盖方向，但仍需把两处真实触点写得更显式。
  - [低] 其他: `validate_internal_hours()` 允许零工时与当前实现兼容，但 `quantity=0` 的语义仍需测试锁定。
  - [低] 其他: 避让上界公式本身正确，风险在于实现时不能把它做成跨调用缓存。
  - [高] 其他: ready_date 字段标签 BUG
  - [中] 可维护性: scheduler.py 的 ready_date 触点需写实到两处
  - [中] 其他: 避让上界必须按调用时状态计算
  - [中] 测试: quantity=0 的零工时语义仍需测试锁定

### M2 · 第二组核验：SGS 评分语义、运行期状态与有序时间线边界

- 状态: 已完成
- 记录时间: 2026-04-07T15:06:53.851Z
- 已审模块: core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/scheduler.py, core/services/scheduler/resource_pool_builder.py, data/repositories/machine_downtime_repo.py, tests/conftest.py, .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md
- 摘要:

  本轮集中核对任务2与任务3，实际下钻了 `dispatch_sgs()` 的评分主干、`batch_order.py` / `sgs.py` / seed 预热三处运行期状态更新，以及 `downtime.py` 的有序时间线假设。

  额外做了两个交叉核验：
  1. 校验 plan 中用 `pytest` 跑脚本式回归是否有效，结果确认 `tests/conftest.py` 已自定义收集 `main()` 风格回归，命令本身是有效的；
  2. 校验 `resource_pool_builder.py` 依赖的停机仓储是否真的按 `start_time ASC` 返回，结果确认服务主链里的停机数据确实有序。

  结论：任务2的主风险仍然是“把程序错误错误地降级成业务不可估算”，这里不仅存在评分主干的大范围 `except Exception`，还存在 `probe_only` 探测的双层吞异常；任务3则出现一个先前未被充分点明的公开边界风险——plan 把 `machine_downtimes` 的有序性完全托付给服务层构建链路，但 `GreedyScheduler.schedule()` 公开入口本身允许 direct-call 直接传入 `machine_downtimes`，如果这些原始片段无序，后续早停优化会把当前兼容边界静默收窄。
- 结论:

  任务2与任务3的总体方向依旧正确，但这里至少有两类必须前置处理的隐患：一类是评分阶段的程序异常吞没（包括 `dispatch_sgs()` 主评分干道与 `probe_only` 探测）；另一类是任务3引入有序前提后对 direct-call `machine_downtimes` 原始输入边界的潜在收窄。除此之外，`runtime_state.py` 共享函数若仅删除 `try/except` 而不调整提交顺序，还会留下“结果已写入、随后又被外层当失败处理”的部分提交风险。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:121-160#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:230-263#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:360-418#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:453-475#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:489-504#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/batch_order.py:58-106#dispatch_batch_order`
  - `core/algorithms/greedy/downtime.py:20-77#occupy_resource`
  - `core/algorithms/greedy/scheduler.py:56-70#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:289-304#GreedyScheduler.schedule`
  - `core/services/scheduler/resource_pool_builder.py:154-160#load_machine_downtimes`
  - `core/services/scheduler/resource_pool_builder.py:301-307#extend_downtime_map_for_resource_pool`
  - `data/repositories/machine_downtime_repo.py:43-55#MachineDowntimeRepository.list_active_after`
  - `tests/conftest.py:18-99#pytest_collect_file`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:372-390#任务 3`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `data/repositories/machine_downtime_repo.py`
  - `tests/conftest.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
- 下一步建议:

  继续核对任务5与剩余低层问题：局部搜索终止性、build_order 缓存、效率测试替身、低风险提示项的真实影响，并据此形成最终结论。
- 问题:
  - [高] 其他: 评分主干广域吞异常
  - [高] 其他: probe_only 探测仍吞程序错误
  - [中] 可维护性: seed 最近状态需要原子绑定更新
  - [高] 其他: 有序时间线前提会收窄 direct-call 停机输入边界
  - [中] 其他: 去掉状态更新吞异常后存在部分提交风险
  - [中] 可维护性: 删除 candidates[0] 前要消灭静默不返回路径
  - [低] 其他: find_earliest_available_start 是否删除需明说

### M3 · 第三组核验：优化器微优化、测试可验证性与最终判定

- 状态: 已完成
- 记录时间: 2026-04-07T15:08:31.371Z
- 已审模块: core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/scheduler.py, core/services/scheduler/calendar_engine.py, .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md
- 摘要:

  最后一轮聚焦任务5与剩余尾项，重点复核三件事：

  1. `optimize_schedule()` 与 `_run_multi_start()` 的微优化是否真能做到“少做重复工作而不引入新隐患”；
  2. 计划中的回归与基准是否真的能测到想测的东西，而不是留下假通过；
  3. 前两轮未完全定性的低层问题，哪些只是提示项，哪些仍会影响最终结论。

  核对结果：
  - `build_order()` 的重复执行确实存在，plan 的缓存方案简洁且正确；
  - 局部搜索终止性当前由 `it += 1` 先执行保证，plan 只要保持这一顺序即可；
  - 效率测试若不直接用替身日历而穿过 `CalendarEngine.get_efficiency()`，会被引擎层 `or 1.0` 先行抹平，导致任务1/2的算法层清理得不到真实验证；
  - `sgs.py:97` 的 `isinstance(exc, Exception)` 属于冗余，不是结构性问题；`auto_assign.py` 的闭包变量捕获方式经核对是安全的，任务1重构后也会自然消失；`seen_hashes` 的内存压力在 plan 设定的 shake 重置下可接受，不构成阻断。
- 结论:

  综合三轮结果，plan 仍然是一份可以落地、且整体上较为优雅的重构方案，但当前文本距离“足够严谨、不会因细节遗漏而悄悄破功”还差最后一轮收口。真正需要前置修正的高风险项现在明确为五类：`ready_date` 字段标签 BUG、SGS 评分主干吞异常、`probe_only` 探测吞异常、`created_at` strict 启用时序错误、以及任务3对 direct-call 停机片段有序性的静默收窄风险。其余项大多属于测试锁定、实现顺序或收尾说明问题。
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:300-334#_run_multi_start`
  - `core/services/scheduler/schedule_optimizer.py:135-140#_run_local_search`
  - `core/services/scheduler/schedule_optimizer.py:359-401#optimize_schedule`
  - `core/algorithms/greedy/dispatch/sgs.py:91-99#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327#dispatch_sgs`
  - `core/algorithms/greedy/auto_assign.py:163-175#auto_assign_internal_resources`
  - `core/algorithms/greedy/scheduler.py:491-496#GreedyScheduler._schedule_internal`
  - `core/services/scheduler/calendar_engine.py:221-222#CalendarEngine.get_efficiency`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:493-518#任务 5`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/calendar_engine.py`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
- 下一步建议:

  据此给出最终结论：保留 plan 主框架，但先修正文中高风险项与新增边界项，再进入实施。
- 问题:
  - [高] 其他: created_at strict 启用时序错误
  - [中] 测试: 效率测试必须绕过引擎层抄底
  - [中] 其他: 局部搜索去重必须保持迭代推进顺序
  - [低] 性能: build_order 重复构造已被准确识别
  - [低] 可维护性: strict_mode 冗余判断应顺手清掉

## 最终结论

结论：有条件通过。

这份 plan 的主框架、拆分方向与目标对齐关系已经通过再次核验：它确实有能力把统一内部工时估算、评分语义收口、日期字段边界收口与优化器去重/微优化落到真实调用链上，且整体设计仍然相对克制，没有引入新的并行路径、额外快速分支或新的广域兜底。

但在真正开始实现前，仍有五个高风险点必须先写回 plan 并锁定实现顺序，否则会出现“方向正确、落地时悄悄失真”的情况：
1. `schedule_optimizer.py` 的 `ready_date` 字段标签 BUG；
2. `dispatch_sgs()` 评分主干广域吞异常；
3. `probe_only` 探测双层吞异常；
4. `optimize_schedule()` 中 `created_at` strict 只能由当前轮 `keys` 决定，而现有构造顺序做不到；
5. 任务3对 direct-call `machine_downtimes` 的有序性假设会静默收窄公开入口兼容边界。

除此之外，还有三类中风险约束也应一并补入 plan 文本：
- `estimate_internal_slot()` 的上界必须在每次调用入口按当前时间线状态计算；
- `runtime_state` 共享后要避免“结果已写入、随后状态更新抛错”的部分提交；
- 效率回归必须直接用替身日历验证算法层，不得穿过引擎层抄底。

因此，本轮 review 不支持“按当前文本直接开做”，但支持“先修正文案与边界说明，再按该 plan 实施”。修正后，这份方案仍是目前最可行、也最简洁的一条路线。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnoqrpx6-7hkd0f",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T15:11:28.048Z",
  "finalizedAt": "2026-04-07T15:11:28.048Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan-17项问题全面核验",
    "date": "2026-04-07",
    "overview": "围绕既有17项问题，对plan目标可达成性、实现优雅性、静默回退清理完整性与剩余BUG风险做一次新的深度review。"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构plan-17项问题全面核验\n\n- 日期：2026-04-07\n- 范围：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其关联算法实现、调用链、测试覆盖点\n- 目标：逐项核实既有17项问题是否成立，检查plan是否足以达成目标，是否仍存在遗漏、逻辑缝隙、过度兜底或静默回退残留\n\n## 审查准则\n1. 结论必须回到真实代码、真实调用链、真实变量流。\n2. 不只看单点函数，还要看上游入参约束、下游消费语义、测试可验证性。\n3. 对高风险项优先核验其是否会直接破坏plan的核心承诺：统一估算、统一打分、显式失败、避免静默退化。"
  },
  "summary": {
    "latestConclusion": "结论：有条件通过。\n\n这份 plan 的主框架、拆分方向与目标对齐关系已经通过再次核验：它确实有能力把统一内部工时估算、评分语义收口、日期字段边界收口与优化器去重/微优化落到真实调用链上，且整体设计仍然相对克制，没有引入新的并行路径、额外快速分支或新的广域兜底。\n\n但在真正开始实现前，仍有五个高风险点必须先写回 plan 并锁定实现顺序，否则会出现“方向正确、落地时悄悄失真”的情况：\n1. `schedule_optimizer.py` 的 `ready_date` 字段标签 BUG；\n2. `dispatch_sgs()` 评分主干广域吞异常；\n3. `probe_only` 探测双层吞异常；\n4. `optimize_schedule()` 中 `created_at` strict 只能由当前轮 `keys` 决定，而现有构造顺序做不到；\n5. 任务3对 direct-call `machine_downtimes` 的有序性假设会静默收窄公开入口兼容边界。\n\n除此之外，还有三类中风险约束也应一并补入 plan 文本：\n- `estimate_internal_slot()` 的上界必须在每次调用入口按当前时间线状态计算；\n- `runtime_state` 共享后要避免“结果已写入、随后状态更新抛错”的部分提交；\n- 效率回归必须直接用替身日历验证算法层，不得穿过引擎层抄底。\n\n因此，本轮 review 不支持“按当前文本直接开做”，但支持“先修正文案与边界说明，再按该 plan 实施”。修正后，这份方案仍是目前最可行、也最简洁的一条路线。",
    "recommendedNextAction": "先修改 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`，把五个高风险点与三类中风险实现约束明确写入；修订完成后再进入实现，不要按当前文本直接编码。",
    "reviewedModules": [
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/common/strict_parse.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/algorithms/sort_strategies.py",
      "core/services/scheduler/calendar_engine.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/downtime.py",
      "core/services/scheduler/resource_pool_builder.py",
      "data/repositories/machine_downtime_repo.py",
      "tests/conftest.py",
      ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
      "core/services/scheduler/schedule_optimizer_steps.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 21,
    "severity": {
      "high": 5,
      "medium": 8,
      "low": 8
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一组核验：服务主链、统一估算入口与日期边界",
      "status": "completed",
      "recordedAt": "2026-04-07T15:05:14.244Z",
      "summaryMarkdown": "本轮先沿 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 主链核对 plan 的任务1与任务4，重点检查三类问题：\n\n1. 统一内部工时入口是否会收窄 direct-call 原始输入边界；\n2. `ready_date` / `created_at` 的 strict 与 non-strict 边界是否真的落在实际消费点；\n3. 优化器与调度器两侧的日期解析标签、调用顺序、异常语义是否一致。\n\n结论：plan 的大方向仍然正确，任务1与任务4确实能达成“统一估算 + 单一日期事实源”的目标，但现有文本里对 `ready_date` 的两处真实消费点写得还不够落地，`schedule_optimizer.py` 的 `ready_date` 字段标签 BUG 则是实打实的高风险现存问题。与此同时，关于避让上界的讨论里，核心风险不在公式本身，而在实现时是否按“每次调用时的当前时间线状态”取值。",
      "conclusionMarkdown": "任务1与任务4可以达成目标，但必须先补齐 `ready_date` 的真实落点说明，并修掉优化器中的字段标签 BUG。原先被归为高严重度的“避让上界”问题，经再次核对，更准确地说是实现约束而不是 plan 结构性缺陷：公式本身成立，关键在于不得把上界预缓存到调用时之外。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 262,
          "lineEnd": 281,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 387,
          "lineEnd": 421,
          "symbol": "collect_schedule_run_input"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 113,
          "lineEnd": 128,
          "symbol": "orchestrate_schedule_run"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 128,
          "lineEnd": 145,
          "symbol": "_build_algo_operations_outcome"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 228,
          "lineEnd": 237,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 488,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 102,
          "lineEnd": 112,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 401,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 85,
          "lineEnd": 102,
          "symbol": "parse_optional_date"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py",
          "lineStart": 7,
          "lineEnd": 41,
          "symbol": "parse_date"
        },
        {
          "path": "core/algorithms/sort_strategies.py",
          "lineStart": 117,
          "lineEnd": 125,
          "symbol": "FIFOStrategy.sort"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py",
          "lineStart": 221,
          "lineEnd": 222,
          "symbol": "CalendarEngine.get_efficiency"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/common/strict_parse.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/algorithms/sort_strategies.py",
        "core/services/scheduler/calendar_engine.py"
      ],
      "recommendedNextAction": "继续下钻任务2与任务3，重点核对 `dispatch_sgs()` 的异常语义、`runtime_state` 收口后的状态一致性，以及有序时间线假设是否会收窄 direct-call 边界。",
      "findingIds": [
        "F-主链引用关系与-plan-前提一致-任务1-4拆分方向成立",
        "F-other-2",
        "F-other-3",
        "F-other-4",
        "F-避让上界公式本身正确-风险在于实现时不能把它做成跨调用缓存",
        "R1-F05",
        "R1-F04",
        "R1-F02",
        "R1-F01"
      ]
    },
    {
      "id": "M2",
      "title": "第二组核验：SGS 评分语义、运行期状态与有序时间线边界",
      "status": "completed",
      "recordedAt": "2026-04-07T15:06:53.851Z",
      "summaryMarkdown": "本轮集中核对任务2与任务3，实际下钻了 `dispatch_sgs()` 的评分主干、`batch_order.py` / `sgs.py` / seed 预热三处运行期状态更新，以及 `downtime.py` 的有序时间线假设。\n\n额外做了两个交叉核验：\n1. 校验 plan 中用 `pytest` 跑脚本式回归是否有效，结果确认 `tests/conftest.py` 已自定义收集 `main()` 风格回归，命令本身是有效的；\n2. 校验 `resource_pool_builder.py` 依赖的停机仓储是否真的按 `start_time ASC` 返回，结果确认服务主链里的停机数据确实有序。\n\n结论：任务2的主风险仍然是“把程序错误错误地降级成业务不可估算”，这里不仅存在评分主干的大范围 `except Exception`，还存在 `probe_only` 探测的双层吞异常；任务3则出现一个先前未被充分点明的公开边界风险——plan 把 `machine_downtimes` 的有序性完全托付给服务层构建链路，但 `GreedyScheduler.schedule()` 公开入口本身允许 direct-call 直接传入 `machine_downtimes`，如果这些原始片段无序，后续早停优化会把当前兼容边界静默收窄。",
      "conclusionMarkdown": "任务2与任务3的总体方向依旧正确，但这里至少有两类必须前置处理的隐患：一类是评分阶段的程序异常吞没（包括 `dispatch_sgs()` 主评分干道与 `probe_only` 探测）；另一类是任务3引入有序前提后对 direct-call `machine_downtimes` 原始输入边界的潜在收窄。除此之外，`runtime_state.py` 共享函数若仅删除 `try/except` 而不调整提交顺序，还会留下“结果已写入、随后又被外层当失败处理”的部分提交风险。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 121,
          "lineEnd": 160,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 230,
          "lineEnd": 263,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 360,
          "lineEnd": 418,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 453,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 489,
          "lineEnd": 504,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 58,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 77,
          "symbol": "occupy_resource"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 70,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 289,
          "lineEnd": 304,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 154,
          "lineEnd": 160,
          "symbol": "load_machine_downtimes"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 301,
          "lineEnd": 307,
          "symbol": "extend_downtime_map_for_resource_pool"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py",
          "lineStart": 43,
          "lineEnd": 55,
          "symbol": "MachineDowntimeRepository.list_active_after"
        },
        {
          "path": "tests/conftest.py",
          "lineStart": 18,
          "lineEnd": 99,
          "symbol": "pytest_collect_file"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 372,
          "lineEnd": 390,
          "symbol": "任务 3"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/scheduler.py",
        "core/services/scheduler/resource_pool_builder.py",
        "data/repositories/machine_downtime_repo.py",
        "tests/conftest.py",
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
      ],
      "recommendedNextAction": "继续核对任务5与剩余低层问题：局部搜索终止性、build_order 缓存、效率测试替身、低风险提示项的真实影响，并据此形成最终结论。",
      "findingIds": [
        "R2-F04",
        "R3-F02",
        "R1-F03",
        "N2-F01",
        "N2-F02",
        "R2-F01",
        "R2-F06"
      ]
    },
    {
      "id": "M3",
      "title": "第三组核验：优化器微优化、测试可验证性与最终判定",
      "status": "completed",
      "recordedAt": "2026-04-07T15:08:31.371Z",
      "summaryMarkdown": "最后一轮聚焦任务5与剩余尾项，重点复核三件事：\n\n1. `optimize_schedule()` 与 `_run_multi_start()` 的微优化是否真能做到“少做重复工作而不引入新隐患”；\n2. 计划中的回归与基准是否真的能测到想测的东西，而不是留下假通过；\n3. 前两轮未完全定性的低层问题，哪些只是提示项，哪些仍会影响最终结论。\n\n核对结果：\n- `build_order()` 的重复执行确实存在，plan 的缓存方案简洁且正确；\n- 局部搜索终止性当前由 `it += 1` 先执行保证，plan 只要保持这一顺序即可；\n- 效率测试若不直接用替身日历而穿过 `CalendarEngine.get_efficiency()`，会被引擎层 `or 1.0` 先行抹平，导致任务1/2的算法层清理得不到真实验证；\n- `sgs.py:97` 的 `isinstance(exc, Exception)` 属于冗余，不是结构性问题；`auto_assign.py` 的闭包变量捕获方式经核对是安全的，任务1重构后也会自然消失；`seen_hashes` 的内存压力在 plan 设定的 shake 重置下可接受，不构成阻断。",
      "conclusionMarkdown": "综合三轮结果，plan 仍然是一份可以落地、且整体上较为优雅的重构方案，但当前文本距离“足够严谨、不会因细节遗漏而悄悄破功”还差最后一轮收口。真正需要前置修正的高风险项现在明确为五类：`ready_date` 字段标签 BUG、SGS 评分主干吞异常、`probe_only` 探测吞异常、`created_at` strict 启用时序错误、以及任务3对 direct-call 停机片段有序性的静默收窄风险。其余项大多属于测试锁定、实现顺序或收尾说明问题。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 334,
          "symbol": "_run_multi_start"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 135,
          "lineEnd": 140,
          "symbol": "_run_local_search"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 401,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 91,
          "lineEnd": 99,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 175,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 496,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py",
          "lineStart": 221,
          "lineEnd": 222,
          "symbol": "CalendarEngine.get_efficiency"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 493,
          "lineEnd": 518,
          "symbol": "任务 5"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/scheduler.py",
        "core/services/scheduler/calendar_engine.py",
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
      ],
      "recommendedNextAction": "据此给出最终结论：保留 plan 主框架，但先修正文中高风险项与新增边界项，再进入实施。",
      "findingIds": [
        "R3-F04",
        "R2-F07",
        "R3-F03",
        "R1-F06",
        "R3-F01"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-主链引用关系与-plan-前提一致-任务1-4拆分方向成立",
      "severity": "low",
      "category": "other",
      "title": "主链引用关系与 plan 前提一致，任务1/4拆分方向成立。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-2",
      "severity": "low",
      "category": "other",
      "title": "`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 仍写死 `field=\"due_date\"`，这是现存 BUG，不修会直接破坏字段级 strict 边界。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-3",
      "severity": "low",
      "category": "other",
      "title": "`scheduler.py` 内 `ready_date` 既在 `BatchForSort` 构造处消费，也在 `batch_progress` 初始化处消费；plan 文本已覆盖方向，但仍需把两处真实触点写得更显式。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-4",
      "severity": "low",
      "category": "other",
      "title": "`validate_internal_hours()` 允许零工时与当前实现兼容，但 `quantity=0` 的语义仍需测试锁定。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-避让上界公式本身正确-风险在于实现时不能把它做成跨调用缓存",
      "severity": "low",
      "category": "other",
      "title": "避让上界公式本身正确，风险在于实现时不能把它做成跨调用缓存。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F05",
      "severity": "high",
      "category": "other",
      "title": "ready_date 字段标签 BUG",
      "descriptionMarkdown": "`schedule_optimizer.py:335-341` 的 `_parse_date()` 在 strict 与 non-strict 两支里都写死了 `field=\"due_date\"`，但 `line 367` 实际拿它解析 `ready_date`。这会把坏 `ready_date` 伪装成 `due_date` 报错，直接破坏任务4想建立的字段级边界。该问题不是推演风险，而是当前代码已存在的实际 BUG。",
      "recommendationMarkdown": "任务4必须显式拆成 `_parse_due_date()` 与 `_parse_ready_date()`，并让坏 `ready_date` 只以 `field=\"ready_date\"` 抛错。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 367,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F04",
      "severity": "medium",
      "category": "maintainability",
      "title": "scheduler.py 的 ready_date 触点需写实到两处",
      "descriptionMarkdown": "`GreedyScheduler.schedule()` 内 `ready_date` 不是只在一个地方消费。`line 145` 会把它放进 `BatchForSort`，`line 228-237` 又会把它转成 `batch_progress` 下界。plan 目前已经表达出“scheduler.py 中 ready_date 要做 strict/non-strict 收口、且不再对日历异常静默回退”的方向，但如果实施者只盯住排序构造处，就会遗漏 `batch_progress` 初始化处，造成同一字段在同一文件内仍有两套边界语义。",
      "recommendationMarkdown": "在任务4步骤4里把 `scheduler.py:145` 与 `scheduler.py:228-237` 两个触点分别列出，避免只改一半。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 228,
          "lineEnd": 237,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F02",
      "severity": "medium",
      "category": "other",
      "title": "避让上界必须按调用时状态计算",
      "descriptionMarkdown": "再次核对 `scheduler.py:510-535` 与 `auto_assign.py:183-206` 可知，plan 提出的上界公式 `N_machine + N_operator + N_downtime + 1` 是成立的，核心目的正是取代固定 `200` 次上限。真正需要防止的不是公式失效，而是实现时把该上界缓存到调用时之外：`machine_timeline` 与 `operator_timeline` 会在排产过程中增长，所以只能在 `estimate_internal_slot()` 每次进入时按当时看到的片段数计算。该项更像实现约束，而不是 plan 架构性错误。",
      "recommendationMarkdown": "把任务1中的上界说明改写成“由 `estimate_internal_slot()` 在每次调用入口按当前时间线长度计算”，避免被实现成预缓存常量。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 510,
          "lineEnd": 535,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 183,
          "lineEnd": 206,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F01",
      "severity": "medium",
      "category": "test",
      "title": "quantity=0 的零工时语义仍需测试锁定",
      "descriptionMarkdown": "当前 `_schedule_internal()` 与 `auto_assign_internal_resources()` 都允许 `setup_hours + unit_hours * quantity == 0` 通过，这与 plan 想保留的零时长工序兼容；但 `quantity=0, unit_hours>0` 与 `setup_hours=0, unit_hours=0` 在业务含义上并不相同。若不加测试，后续实现者可能在统一入口里无意收紧或放宽这一边界。",
      "recommendationMarkdown": "在任务1测试中单列 `quantity=0, unit_hours>0` 场景，明确它是兼容性保留还是应视作坏数据。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 488,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 102,
          "lineEnd": 112,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F04",
      "severity": "high",
      "category": "other",
      "title": "评分主干广域吞异常",
      "descriptionMarkdown": "`dispatch_sgs()` 当前在候选评分主循环外层保留了大范围 `except Exception`，见 `sgs.py:360-418`。这会把 `AttributeError`、`KeyError`、`NameError` 乃至接口契约违背都压扁成“最差但可比较”的 key，继续参与排序。由于 plan 的核心承诺之一就是把意外程序错误与业务不可估算彻底分离，这一类异常吞没必须在实施前被明确拔掉，否则任务2虽然做了拆分，语义上仍没有真正完成。",
      "recommendationMarkdown": "拆分后的 `_score_internal_candidate()`、`_score_external_candidate()` 与候选循环主干都不应再保留这类广域异常降级；对外只允许五类明确业务不可估算原因生成降级 key。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 360,
          "lineEnd": 418,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F02",
      "severity": "high",
      "category": "other",
      "title": "probe_only 探测仍吞程序错误",
      "descriptionMarkdown": "`sgs.py:230-263` 的 `probe_only=True` 自动分配探测存在双层 `except Exception`：内层处理返回值解构，外层包住整个自动分配调用。结果是探测返回形状错误、自动分配内部异常、调用契约错误都会被等价折叠成“缺资源且无法自动分配”。这与任务2想建立的显式失败语义直接冲突，且影响面比一般提示性问题更大，因为它会静默改变候选优先级。",
      "recommendationMarkdown": "把两层 `except Exception` 全部删掉，只保留 `chosen is None` 的正常分支；同时补一条回归，断言探测返回坏形状或抛异常时会直接暴露，而不是转成降级 key。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 230,
          "lineEnd": 263,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F03",
      "severity": "medium",
      "category": "maintainability",
      "title": "seed 最近状态需要原子绑定更新",
      "descriptionMarkdown": "seed 预热与正式派工的最近状态语义并不相同。`scheduler.py:299-304` 中 `last_end_by_machine` 与 `last_op_type_by_machine` 是绑在同一个“更晚 end_time”条件上的；而 `batch_order.py:95-106` 与 `sgs.py:463-475` 则是 `last_end_by_machine` 条件覆盖、`last_op_type_by_machine` 非空即直接覆盖。plan 已识别这两种模式，但共享函数设计若只做布尔开关、没有保证 seed 分支里的原子绑定，就会把 seed 语义做坏。",
      "recommendationMarkdown": "`runtime_state.py` 里 seed 模式要么单独函数实现，要么保证 `last_end_by_machine` 与 `last_op_type_by_machine` 在同一条件分支里同时更新。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 299,
          "lineEnd": 304,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 95,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 463,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "N2-F01",
      "severity": "high",
      "category": "other",
      "title": "有序时间线前提会收窄 direct-call 停机输入边界",
      "descriptionMarkdown": "任务3计划把 `find_overlap_shift_end()` 与 `find_earliest_available_start()` 建立在“输入片段已经有序”的前提上，并明确写到 `machine_downtimes` 继续依赖 `resource_pool_builder.py` 的排序保证。服务主链这一点确实成立：`MachineDowntimeRepository.list_active_after()` 通过 `ORDER BY start_time ASC, id ASC` 返回数据，`resource_pool_builder.py` 只是顺序装入列表。但 `GreedyScheduler.schedule()` 是公开算法入口，签名直接允许外部调用方传入 `machine_downtimes` 原始字典。当前代码即使面对无序片段也能工作，因为 `find_overlap_shift_end()` 全量扫描、`find_earliest_available_start()` 还会自行 `sorted(...)`。如果按 plan 直接移除这些兜底而不在公开入口做一次归一化，就会对 direct-call 形成静默兼容性收窄：无序停机片段可能被早停逻辑漏检，直接排进停机窗口。",
      "recommendationMarkdown": "不要只依赖服务层排序保证。更稳妥的做法是在 `GreedyScheduler.schedule()` 或新估算器入口对外部传入的 `machine_downtimes[mid]` 做一次轻量标准化，或把“公开入口要求有序停机片段”明文写进 plan 与回归。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 64,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 31,
          "lineEnd": 77,
          "symbol": "find_earliest_available_start"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 154,
          "lineEnd": 160,
          "symbol": "load_machine_downtimes"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 301,
          "lineEnd": 307,
          "symbol": "extend_downtime_map_for_resource_pool"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py",
          "lineStart": 43,
          "lineEnd": 55,
          "symbol": "MachineDowntimeRepository.list_active_after"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 372,
          "lineEnd": 379,
          "symbol": "任务 3"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "N2-F02",
      "severity": "medium",
      "category": "other",
      "title": "去掉状态更新吞异常后存在部分提交风险",
      "descriptionMarkdown": "当前 `batch_order.py` 与 `sgs.py` 都是在 `result` 已经 append、`batch_progress` 已推进、`scheduled_count` 已累加之后，才做忙时与最近状态更新；只是靠内层 `try/except` 把这些更新异常吃掉了，所以不会触发外层失败分支。一旦按 plan 去掉内层吞异常、改成共享 `runtime_state.py` 小函数，若该小函数抛异常，外层 `except` 会把同一工序再次计入失败并阻断批次，而先前写进 `results` 的成功结果却不会回滚，形成“已成功又失败”的部分提交状态。",
      "recommendationMarkdown": "共享状态更新要么放到“提交结果”之前执行，要么做成对当前已守卫输入完全无异常的纯字典更新，避免仅靠删除 `try/except` 却留下部分提交。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 58,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 453,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 489,
          "lineEnd": 504,
          "symbol": "dispatch_sgs"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 381,
          "lineEnd": 390,
          "symbol": "任务 3"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F01",
      "severity": "medium",
      "category": "maintainability",
      "title": "删除 candidates[0] 前要消灭静默不返回路径",
      "descriptionMarkdown": "`sgs.py:424-425` 当前的 `best_pair = candidates[0]` 的确是死代码，但它实际上承担了最后一道“所有候选都没产出 key”时的兜底。plan 的删除方向是对的，不过如果拆分后的 `_score_internal_candidate()` / `_score_external_candidate()` 仍保留“既不返回 key 也不抛异常”的路径，删除这行后就会把逻辑问题从静默劣化变成 `best_pair is None` 的运行时故障。",
      "recommendationMarkdown": "删除 `candidates[0]` 之前，先用显式返回类型和回归用例锁死：每个评分分支不是返回正常 key，就是返回明确的业务不可估算 key，剩下的都直接抛异常。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 420,
          "lineEnd": 425,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F06",
      "severity": "low",
      "category": "other",
      "title": "find_earliest_available_start 是否删除需明说",
      "descriptionMarkdown": "当前 `find_earliest_available_start()` 只被 `sgs.py` 的内部评分近似路径使用。plan 的任务2完成后，这条路径原则上应消失；如果函数随后仍保留，就连同其中的 `except Exception: dur = 0.0` 一起保留了一个已知静默回退残留。它不是当前主阻断，但需要在实施收尾时明确说明“已删除”还是“作为范围外遗留保留”。",
      "recommendationMarkdown": "任务2完成后立刻复核此函数的引用；若无引用，直接删掉；若保留，需在完成判定中把它列为范围外残留。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 31,
          "lineEnd": 41,
          "symbol": "find_earliest_available_start"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 15,
          "lineEnd": 15,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 310,
          "lineEnd": 319,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "data/repositories/machine_downtime_repo.py"
        },
        {
          "path": "tests/conftest.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F04",
      "severity": "high",
      "category": "other",
      "title": "created_at strict 启用时序错误",
      "descriptionMarkdown": "`optimize_schedule()` 当前在 `line 359-370` 先构造 `batch_for_sort`，随后才在 `line 392-401` 得到 `valid_strategies` 与 `keys`。但任务4要求 `created_at` 的 strict 只在当前轮次 `keys` 真正包含 `fifo` 时启用。也就是说，plan 的目标语义是正确的，但现有代码执行顺序与目标语义相互矛盾：如果不先调整顺序，就根本无法按 `keys` 决定 `created_at` 是否严格校验。",
      "recommendationMarkdown": "把 `valid_strategies` / `keys` 的确定提前到 `batch_for_sort` 构造之前，或把 `created_at` 的 strict 解析延迟到已知 `keys` 之后；就当前结构而言，前移顺序是更简洁的修法。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 401,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F07",
      "severity": "medium",
      "category": "test",
      "title": "效率测试必须绕过引擎层抄底",
      "descriptionMarkdown": "算法层当前有三处效率读取：`scheduler.py:494`、`auto_assign.py:166-169`、`sgs.py:323-327`。计划要清掉算法层的 `or 1.0` 与外层吞异常，但 `CalendarEngine.get_efficiency()` 自身仍在 `line 221-222` 做 `or 1.0`。因此，如果测试不是直接注入替身日历，而是穿过真实引擎层，就无法证明算法层的清理是否生效，容易得到“测试绿了但目标没真正达成”的假结论。",
      "recommendationMarkdown": "保留 plan 里的替身日历做法，并把“不得穿过 `CalendarEngine` 验证 0.0 效率”写得更硬一些，避免测试实现跑偏。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 496,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 169,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py",
          "lineStart": 221,
          "lineEnd": 222,
          "symbol": "CalendarEngine.get_efficiency"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F03",
      "severity": "medium",
      "category": "other",
      "title": "局部搜索去重必须保持迭代推进顺序",
      "descriptionMarkdown": "当前 `_run_local_search()` 在 `while` 体一开始先做 `it += 1`，然后才会构造邻域。plan 要加入 `seen_hashes` 去重，如果把去重判断放到 `it += 1` 之前，就会在“所有邻域都重复”的小规模场景里留下无限循环风险。现有代码已经给出了正确顺序，plan 只需要明确保持，不需要另造复杂终止机制。",
      "recommendationMarkdown": "在任务5步骤4里明确写出：`it += 1` 必须先于去重判断执行；重复邻域只是不计入 `attempts`，不是不计入迭代。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 135,
          "lineEnd": 140,
          "symbol": "_run_local_search"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 512,
          "lineEnd": 518,
          "symbol": "任务 5"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F06",
      "severity": "low",
      "category": "performance",
      "title": "build_order 重复构造已被准确识别",
      "descriptionMarkdown": "`_run_multi_start()` 里 `build_order(strat, params0)` 当前确实位于 `dispatch_rule` 内层循环，见 `schedule_optimizer_steps.py:331-334`。而排序结果只取决于 `strategy` 与 `params0`，与 `dispatch_mode` / `dispatch_rule` 无关，所以 plan 用 `(strategy.value, tuple(sorted(params0.items())))` 做缓存是正确且简洁的，不会引入额外语义分叉。",
      "recommendationMarkdown": "该项无须额外升级，只要照 plan 方案做即可。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 334,
          "symbol": "_run_multi_start"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 504,
          "lineEnd": 510,
          "symbol": "任务 5"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F01",
      "severity": "low",
      "category": "maintainability",
      "title": "strict_mode 冗余判断应顺手清掉",
      "descriptionMarkdown": "`sgs.py:96-99` 中 `except Exception as exc:` 之后又写 `if strict_mode and isinstance(exc, Exception): raise`，其中 `isinstance(exc, Exception)` 永远为真。这不是结构性问题，但会在重构时制造噪音，建议顺手删成 `if strict_mode: raise`。",
      "recommendationMarkdown": "改造 `avg_proc_hours` 初始化段时一并清理，不要把冗余判断带入新代码。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 96,
          "lineEnd": 99,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/calendar_engine.py"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:4ffe4b3361e13806217e06c7da1d7efee9be22d1d259c9b8772f0e38b21b64b6",
    "generatedAt": "2026-04-07T15:11:28.048Z",
    "locale": "zh-CN"
  }
}
```
