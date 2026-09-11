---
doc_type: issue-fix
issue: 2026-09-08-unselected-execution-resource-guardrails
path: fast-track
fix_date: 2026-09-08
tags:
  - scheduler
  - execution-facts
  - resource-reservation
  - adopted-only
  - feedback-continuity
---

# 未选中在制工序资源保护与报工连续性

## 1. 最终结论

- 已完成资源保护和范围修正。**仅在正式发布且存在未选中的 processing/paused 工序时 fail closed**；模拟仍正确避让。已选在制工序的正式重排路径保留，不新增全局禁用。
- 模拟中 B1 实际 08:00 开工、计划时长 1 小时，08:30 只排 B2：B2 09:00 开工。未选 B1 不进入结果、生产计数、批次状态回写。
- 被拒绝的正式发布不消耗版本，不改变原执行事件/计划；测试已证明 B1 可以继续使用原版本、原 schedule_id 和真实 revision 提交 finish。完工后 B2 可以正常发布。
- 不放松 adopted-only/latest guard，不迁移执行身份，不复制或伪造 start 事件，不无条件合并旧 pending 计划。
- 中途误加的“所有在制均禁止正式发布”已撤销；不通过修复未选范围的问题改变已选重排合同，也不提示“全选即可继承开工记录”。

## 2. 两层真实根因

### 资源事实漏读

`schedule_input_collector._load_batches_and_operations` 只加载选中批次，符合重排范围约定；错误在于 `_collect_execution_guardrails` 继续用这些 op_ids 截断事实，把“不参与重排”当成“不占用资源”。只扩大到全局 latest version 仍不够：partial 版本可能已经没有 B1。

现在 `schedule_execution_resource_facts.py:24` 按每道工序的最后正式计划身份查找，再交给既有 `ExecutionFactProvider` 按完整身份读取。snapshot 覆盖未选未开工工序，计算期间新增 start 也能被发现。fixed/completed 执行种子仍只针对选中工序。

### 发布后报工断链

以下证据来自 Python 3.8.10 的隔离内存库真实 `run_schedule` / `finish_operation`，未修改反馈 guard：

```text
selected=['B2'] new_version=2 new_op_ids=[20]
old_scope_finish=not_current_official_plan
events=[(1, 100, 'start')]

selected=['B1', 'B2'] new_version=2 new_op_ids=[10, 20]
old_scope_finish=not_current_official_plan
new_scope_finish=invalid_state_transition status=not_started
events=[(1, 100, 'start')]
```

代码证据：

- `operation_execution_feedback_service.py:368` 的 `_load_current_official_schedule` 通过 `can_write_feedback` 拒绝非最新正式采用方案，旧 scope 不能继续 finish。
- 同文件 `:120` 之后按请求的完整 scope 读取状态；`:163` 再检查状态转移。
- `operation_execution_event.py:55` 的状态机不允许 not_started 直接 finish。
- `schedule_persistence.py:292` 为新版本构建并插入新 Schedule 行。保留工序、时间和资源不等于保留原 `schedule_version/schedule_id`，也不会带入原 start 事件。

因此，本轮 `schedule_execution_feedback_guard.py:10` **只拦截正式发布遗漏未选在制工序**，不扩大到已选路径，不改数据库身份语义。错误码为 6003，reason=`execution_feedback_continuity_blocks_publish`，附未选在制的 `op_ids/batch_ids/unselected_batch_ids`。文案只说明“未选在制批次不能安全发布，可先完成报工或仅模拟”，不承诺全选能继承开工记录。

### 已全选断链是范围外原行为

只读对照基准 HEAD：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`。通过 `git show` 在内存中加载 HEAD 的 `schedule_input_collector.py`、`schedule_execution_guardrails.py`、`schedule_input_runtime_support.py`，在隔离 SQLite 内存库运行 B1+B2，得到：

```text
HEAD_input_and_guard selected=B1+B2 new_version=2 op_ids=[10, 20] fixed_start=2026-09-08 08:00:00
old_scope=not_current_official_plan status=None
new_scope=invalid_state_transition status=not_started
events=[(1, 100, 'start')]
```

同时核对反馈服务、反馈支持、ExecutionFactProvider、事件状态机、schedule_persistence 五个文件与 HEAD 字节完全相同。以上是 HEAD 输入/护栏配合当前依赖的定点对照，不是整仓 clean HEAD proof；它确认该断链不是本轮引入。本轮保留原行为。独立后续建议：另案处理跨版本执行身份的报工生命周期，先明确正式行与真实执行身份的关系，再验证 finish、幂等、revision 和回滚；本轮不实施、不放松 adopted guard、不伪造 start。

## 3. 最终合同

1. **模拟资源保护**：未选 processing/paused 使用实际设备和实际人员生成本轮占用。设备加入算法设备不可用区间，人员通过本轮 `ExecutionResourceCalendar` 限制最早可用时间；不写机器停机表、人员日历或新方案种子。
2. **选中边界**：未选批次不进入 batches、operations、输出允许集合和生产计数。已选在制工序继续按原路径生成固定执行种子，允许原有正式重排，不移动其实际开工时间/资源。
3. **pending 不冻结**：未选 not_started/pending 仅参与并发快照，不占用资源；未选 completed 也不作为本次结果种子。无未结束事实时仍可正常发布 partial 方案。
4. **身份不混合**：只读取 schedule/adopted/scenario_id=None；新版遗漏某工序时查其最后正式身份。同一工序已有更新正式行时保留原 superseded-scope 规则，不把多个身份事件按 op_id 混合聚合。
5. **并发保护**：`execution-snapshot:resources-v1:` 包含完整身份、事件 revision、实际时间/资源、计划时间和 source；落库前重新发现完整集合，不只遍历旧 expected_op_ids。计算期间首次开工或发生变化会拒绝本轮结果；版本分配后的复查仍在原事务中。
6. **失败关闭**：无效状态/时间/身份、重复正式行、缺失实际资源、实际资源不存在、占用 source 不明确、异常工序均拒绝本轮排程。最终结果与未选占用重叠也拒绝。
7. **发布边界只针对未选在制**：存在未选在制时，正式发布拒绝，即使它与所选资源互不冲突。全部在制已选中时不被本轮 guard 阻止。正常模拟不改 latest，原 finish 仍然可用。
8. **既有历史问题**：历史上已经产生的断链身份可被模拟资源保护读取，但本次不会修复其报工身份，也不会通过放松 guard 让它继续写入。

## 4. 估算边界

- 预计释放沿用既有模型：`实际开工时间 + 对应正式计划结束时间 - 对应正式计划开始时间`。这不是实际完工时间，也不能证明资源现场已经释放。
- 不新增剩余量、暂停延时或效率修正。预计释放不晚于本次排程开始但仍在制时，拒绝并返回 `execution_resource_release_unknown`，不假装已经完工。
- 人员包装层针对已在制人员的最早可用时间；开始时间倒填到真实开工之前时，也不利用该人员的历史空隙。无关人员不受影响。
- 图候选评分仍用原日历容量估算，本修复不声称实现了精确的人员占用容量评分。

## 5. 改变文件

产品文件 9 个：

- `core/services/scheduler/run/schedule_execution_guardrails.py`
- `core/services/scheduler/run/schedule_execution_persistence_guard.py`
- `core/services/scheduler/run/schedule_execution_resource_facts.py`（新增）
- `core/services/scheduler/run/schedule_execution_reservations.py`（新增）
- `core/services/scheduler/run/schedule_execution_feedback_guard.py`（新增）
- `core/services/scheduler/run/schedule_input_collector.py`
- `core/services/scheduler/run/schedule_input_runtime_support.py`
- `core/services/scheduler/run/schedule_seed_contracts.py`（追加授权：等价 helper 提取）
- `core/services/scheduler/run/schedule_input_seed_metadata.py`（追加授权：等价 helper 提取，保留原未跟踪内容的合同）

独立测试 6 个：

- `tests/schedule/service/test_unselected_execution_resource_guardrails.py`
- `tests/schedule/service/test_unselected_execution_resource_snapshot.py`
- `tests/schedule/service/test_unselected_execution_resource_fail_closed.py`
- `tests/schedule/service/test_unselected_execution_feedback_continuity.py`
- `tests/schedule/service/unselected_execution_guardrails_support.py`
- `tests/schedule/service/test_schedule_seed_metadata_helper_contract.py`

加本记录共 16 个文件。runtime_support 原有 `with_frozen_external_seed_metadata` 接入保留；seed_contracts 原有外协元数据转交逻辑保留，仅提取重复的可选文本转换。

追加授权的复杂度收口：`coerce_seed_result_item` CC **16 -> 6**，`with_frozen_external_seed_metadata` CC **27 -> 4**；所提取 helper 最高 CC **10**。没有新增豁免或白名单。保留冻结元数据验证顺序、异常 cause、非 merged 原对象复用、merged 复制、不修改输入和公开序列化边界。

未改 optimizer*、evaluation.py、GreedyScheduler.schedule 的 A3 公开签名、greedy/scheduler.py、共享运行 state、原日历服务、前端、启动打包、共享台账和测试注册。

## 6. 实跑验证

全部测试使用 `.venv/bin/python`，实际版本 Python 3.8.10；数据库只使用 `:memory:` 和 pytest 临时文件库。

最终独立测试：

```bash
.venv/bin/python -m pytest -q tests/schedule/service/test_unselected_execution_resource_guardrails.py tests/schedule/service/test_unselected_execution_resource_snapshot.py tests/schedule/service/test_unselected_execution_resource_fail_closed.py tests/schedule/service/test_unselected_execution_feedback_continuity.py
```

独立测试覆盖设备/人员分别共享、graph off/report/on、自动派工、实际资源不同于计划资源、模拟计数隔离、两版历史 partial 遗漏 B1、异常事实、snapshot 并发、双连接 start、版本回滚、发布拒绝后 finish、重复模拟后 finish、完工后正常发布，以及已选 processing/paused 正式重排仍允许。历史 partial 反例只在隔离库绕过本轮 guard；全选反例直接运行保留的产品路径，无 guard 绕过。

复杂度收口后的最终定点联测：

```bash
.venv/bin/python -m pytest -q tests/schedule/service/test_unselected_execution_resource_guardrails.py tests/schedule/service/test_unselected_execution_resource_snapshot.py tests/schedule/service/test_unselected_execution_resource_fail_closed.py tests/schedule/service/test_unselected_execution_feedback_continuity.py tests/schedule/service/test_schedule_seed_metadata_helper_contract.py tests/algorithm/test_seed_external_group_cache_rebuild.py tests/algorithm/test_algorithms_a3_dependency_boundary.py tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py
```

范围修正后的最终结果 **135 passed in 8.37s**，覆盖本轮 90 个新增用例与既有冻结外协元数据、A3、图模式合同。

扩大回归命令：

```bash
.venv/bin/python -m pytest -q tests/schedule/service tests/operation_execution tests/algorithm/test_seed_external_group_cache_rebuild.py tests/algorithm/test_algorithms_a3_dependency_boundary.py tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py
```

范围修正后的最终结果 **453 passed in 30.83s，剩余失败 0**。此前因过宽发布 guard 失败的 5 个既有用例均恢复通过，没有修改、隐藏或 xfail 它们。

定点静态（均使用 `.venv/bin/python`）：

- `-m ruff check <上述 15 个 Python 文件>`：All checks passed。
- `-m pyright <上述 9 个产品文件>`：0 errors / 0 warnings；未升级依赖。
- `tools/scan_py38plus_syntax.py --fail-on-hit <上述 15 个 Python 文件>`：15 个文件，0 读取失败、0 发现。
- 调用门禁原函数 `scan_complexity_entries` / `scan_oversize_entries` 对 9 个产品文件检查：均为空（阈值 15 / 500 行）。
- `git diff --check` 定点检查：通过。

较早阶段 `scripts/run_quality_gate.py --fast-precheck` 曾退出 1，报告其他并行工作的 8 个 lint 问题。该结果不是最终整合状态；主线程随后告知全仓 Ruff 已通过，本轮最终 15 个文件 Ruff 也实跑通过。按最终协调要求不启动完整门禁或性能任务，源码收敛后交主线程统一执行。

## 7. 剩余限制

- **正式发布遗漏未选在制工序仍会被拒绝**，这是本轮批准的 fail-closed 边界；已选在制正式重排未被禁用。
- 已全选重排后的跨版本报工断链是上面单列的已存在风险，未在本次修复；服务影响面回归没有剩余失败。
- 未做超大历史数据量压力测试；未在 Win7 目标机实跑；未增加运行时依赖。
- 所有本轮文件未提交；原有 staged/dirty/untracked 和过程中其他并行改动未回退、未清理。当前只有 dirty 工作区定点证据，**没有 clean-worktree proof**。
