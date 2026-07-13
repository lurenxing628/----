---
doc_type: audit-finding
audit: 2026-07-13-unpushed-dependency-governance-review
finding_id: "bug-01"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 01：A3 legacy dispatch adapter 绕过 strict-mode 并删除既有执行回退

## 速答

提交 `f422b88c` 新增的 `_LegacyDispatchContext` 不是原 `ScheduleRunContext.from_legacy_scheduler()` 的行为等价替代：它直接丢弃 `strict_mode`，并把原有 canonical scheduling/auto-assign 回退改成缺 callback 就抛 `TypeError`。在公开 `dispatch_batch_order` 入口上，非法工时因此会调用 legacy callback，再退化成没有具体错误原因的普通失败，而不是原先的 `ValidationError` fail-loud。

## 关键证据

- `core/algorithm_runtime/dispatch_context.py:33-39` — `schedule_internal()` 复制 kwargs 后直接 `pop("strict_mode", None)`，没有执行任何严格工时校验，随后调用 legacy `_schedule_internal`。
- `core/algorithms/greedy/run_context.py:53-66` — A3 前 dispatch 使用的原适配路径先取出 `strict_mode`，调用 `_validate_strict_internal_input(...)`，只有校验通过才调用 legacy callback；没有 callback 时还会进入 canonical `schedule_internal_operation(...)`。
- `core/algorithm_runtime/dispatch_context.py:27-48` — 新 adapter 对 external/internal/auto-assign callback 缺失均直接抛 `TypeError`；原 `ScheduleRunContext` 在 `core/algorithms/greedy/run_context.py:47-84` 会分别回退到 canonical `schedule_external`、`schedule_internal_operation` 和 `auto_assign_internal_resources_attempt`。
- `core/algorithms/greedy/dispatch/batch_order.py:40`、`:124-149`、`:186-201` — public batch-order 路径先套新 adapter；除 `ValidationError` 外的异常会被折算成 dispatch failure。由于新 adapter 已不再抛 strict `ValidationError`，非法输入可继续进入 callback。
- `.codestable/refactors/2026-07-12-algorithms-a3-dependency-decoupling/algorithms-a3-dependency-decoupling-refactor-design.md:62`、`:229-233` — 设计明确承诺不改算法/异常行为，且 adapter 只做兼容适配；当前实现违反这一合同。
- `tests/algorithm/test_algorithms_a3_dependency_boundary.py:1-308` — 边界测试覆盖 identity/import/SCC，但没有调用 `ensure_dispatch_context` 或 direct legacy `dispatch_batch_order`；现有 strict SGS 测试会在评分阶段提前拒绝坏工时，也覆盖不到 batch-order adapter。

最小复现（当前 HEAD）：

```text
dispatch_batch_order(
    legacy_scheduler_with__schedule_internal,
    sorted_ops=[setup_hours="not-a-number"],
    strict_mode=True,
    ...
)
=> RETURNED (0, 1)
=> legacy_callback_calls=1
=> errors=[]
```

把同一入口的 context coercion 临时替换回 A3 前仍存在且代码未变的 `ensure_run_context` 后：

```text
=> RAISED ValidationError '[1001] “换型时间”必须是数字'
=> field=setup_hours
=> legacy_callback_calls=0
```

`git blame` 确认 `dispatch_context.py:33-39` 全部来自 `f422b88c`。

## 影响

- **主生产 `GreedyScheduler.schedule()` 路径目前不直接触发**：它在 `core/algorithms/greedy/scheduler.py:124` 先构造完整 `ScheduleRunContext`，新 `ensure_dispatch_context` 会原样返回该对象。
- **受影响的是 A3 明确声称兼容的 direct/legacy dispatch 入口**：仓内测试、脚本或仓外调用方直接把旧 scheduler-like 对象传给 `dispatch_batch_order` 时，strict 合同被绕过。
- 非法工时从“明确字段错误并停止”变成“回调被执行、最终只看到排产失败计数”，属于静默降级和错误原因丢失；若 callback 自身宽容，还可能继续生成本不该生成的排程。
- 缺少私有 callback 的 legacy 对象也从“使用 canonical 实现”变成 `TypeError` 后被主循环折算成普通失败，兼容面进一步收窄。

## 修复方向

先补 characterization test 锁住 A3 前的 legacy 行为，再让 adapter 与原 context 只保留一份语义：至少恢复 strict 工时校验；对缺省 callback 是继续 canonical 回退还是正式收窄合同，必须显式决定并测试，不能由新 adapter 静默改变。若继续兼容，优先抽出中立的共享适配逻辑，避免 `ScheduleRunContext` 与 `_LegacyDispatchContext` 两份近似实现再次漂移。

## 建议动作

`cs-issue`，因为这是已可复现的行为回归和 fail-loud 边界破坏；应在 push 前修复并补合同测试。

## 修复闭环（2026-07-13）

- 已进入 `.codestable/issues/2026-07-13-legacy-dispatch-adapter-contract/` 标准 issue。
- `_LegacyDispatchContext.schedule_internal()` 现在会在 legacy callback 前执行 strict 工时校验，非法 `setup_hours` 重新抛 `ValidationError(field="setup_hours")`，callback 调用数保持 0。
- callback 合同采用“能力按需 fail-loud”：不在 adapter 构造时要求所有 callback；当前执行路径真正缺能力时抛 `DispatchContextContractError(TypeError)`，batch-order / SGS 都明确透传，不再被普通 dispatch failure 折算。
- 没有恢复偶然的 canonical fallback。完整恢复需要把具体 scheduling 算法下沉到 runtime leaf，会扩大为跨模块重构并破坏 A3 职责；当前仓内 missing-batch、auto-assign-disabled 等无需该 callback 的兼容路径由扩大回归证明保持不变。
- 三条新合同测试分别锁定 strict callback 前拒绝、batch-order 缺能力 fail-loud、SGS 缺能力 fail-loud；完整质量门禁 19/19 receipts 均通过，4734 collected、unexpected failure 0。当前工作区未提交，manifest=`passed_but_unbound`，不宣称 clean proof。
