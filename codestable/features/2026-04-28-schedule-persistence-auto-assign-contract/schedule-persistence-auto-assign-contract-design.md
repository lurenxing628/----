---
doc_type: feature-design
feature: 2026-04-28-schedule-persistence-auto-assign-contract
status: approved
summary: 固定排产落库校验、模拟排产和自动分配资源写回合同。
tags: [scheduler, persistence, auto-assign, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: schedule-persistence-auto-assign-contract
---

# 落库校验与自动分配写回合同设计

## 0. 承接边界

PR-6 承接完整 M4 的结果：优化器输出、summary 投影、历史落库读回和页面展示均已有证据。但 PR-6 不能把 M4 的证明当成落库校验和自动分配写回已经稳定；本次必须自己证明 `build_validated_schedule_payload()` 的错误优先级、`simulate=True` 的写入边界，以及 `auto_assign_persist` 的资源补写条件。

明确不做：

- 不新增业务 `if`、fallback、兜底、静默吞错、宽泛默认值、宽泛 `try/except`、新 reason 或新 details。
- 不改 summary、result_summary、schema、页面、route、viewmodel、repo、质量门禁脚本、full-test-debt 脚本和台账脚本运行逻辑。
- 不在持久化层重新解释 `auto_assign_persist`；yes/no 归一化属于配置层。
- 不新增“写自动分配资源前重读数据库工序”的特殊检查；旧对象覆盖风险只作为观察项记录。
- 不减少 full-test-debt；P1-11/12/13 只按 complexity/test_coverage 处理。

## 1. 对外合同

- 落库前错误优先级保持：`out_of_scope_schedule_rows > invalid_schedule_rows > no_actionable_schedule_rows`。
- 全部结果都无效且没有任何可落库行时，仍走 `no_actionable_schedule_rows`，并带 `validation_errors`。
- `simulate=True` 仍可写 Schedule 和 ScheduleHistory 作为追溯，但不能更新 Batches/BatchOperations 状态，也不能持久化自动分配资源。
- `auto_assign_persist=no` 时，正式排产仍可写 Schedule、History 和状态，但不能补写 BatchOperations 的 machine/operator。
- 自动分配资源只针对内部工序、原本缺资源工序、结果中有资源的字段；已有 machine/operator 不覆盖，只缺哪个字段就只补哪个字段。
- 外协结果不进入 internal auto-assign 写回，`missing_internal_resource_op_ids` 不包含的工序不写回资源。

## 2. 实现策略

本次代码改动只允许做一件事：把 `build_validated_schedule_payload()` 里已经存在的判断原样搬到私有 helper。搬移时必须保持错误消息、`reason`、`details`、优先级、source 判定和 `assigned_by_op_id` 形状完全不变；原位置删除同一段判断，不能复制一份再加新分支。

若红灯测试或静态检查证明必须新增特殊处理，立即停线，先说明原因和影响，不直接实现。

## 3. 证据路径

1. 新增 PR-6 专项测试，先锁住错误优先级、simulate 行为和 auto-assign 写回矩阵。
2. 原样搬移 `build_validated_schedule_payload()` 的已有判断到私有 helper，降低复杂度。
3. 跑 PR-6 窄测试、已有落库/服务回归、PR-5 下游页面/报表读取回归。
4. 若复杂度达标，用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 刷新台账。
5. 复跑 full-test-debt、台账检查、yaml 校验、ruff、pyright、`git diff --check` 和最终 clean quality gate。
6. 写 acceptance，回填 roadmap、items.yaml、source-map，并在 PR-7 头部写清不能继承 PR-6 的页面 proof。

## 4. 验收契约

- 错误优先级测试覆盖 out-of-scope 与 invalid 同时出现、invalid 与有效行同时出现、全部非法但没有可落库行三类场景。
- `simulate=True` 不改批次状态、工序状态和自动分配资源，同时保持现有 Schedule/History 追溯语义。
- `auto_assign_persist=no`、外协结果、已有资源、只缺 machine、只缺 operator、缺两者、missing set 门控均有测试。
- `build_validated_schedule_payload()` 复杂度登记如果被移除，只写 complexity 关闭；如果未移除，停线说明，不为关闭登记新增逻辑。
- 不新增 fallback、兜底、静默吞错，不改 summary/页面/repo，不减少 full-test-debt。

## 5. 观察项

- 当前 `BatchOperationRepository.update()` 是通用更新接口，不在本轮改成“不覆盖资源”的专用接口。
- “传入 op 对象资源为空，但数据库当前行已被别处补资源”的并发/旧对象风险，本轮不处理；如后续要治理，应另开任务评估是否需要写前重读或专用更新接口。
