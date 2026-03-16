# 全量自测审阅报告（LLM）

- 时间：2026-03-16 10:27
- 证据：
  - `evidence/FullSelfTest/full_selftest_report.md`
  - `evidence/FullSelfTest/logs/75_regression_optimizer_ortools_logging_exc_info_safe.py.log.txt`
  - `evidence/FullSelfTest/logs/77_regression_ortools_budget_guard_skip_when_no_time.py.log.txt`
  - `evidence/FullSelfTest/logs/82_regression_priority_weight_case_insensitive.py.log.txt`

## 事实摘要（来自证据）

- 总体结论：FAIL
- 汇总记录数：137
- 通过范围：10 个 smoke、2 个 web smoke、1 个 FullE2E、复杂 Excel 用例，以及其余 134 个 regression 中的 131 个均通过。
- 失败项 1：`regression_optimizer_ortools_logging_exc_info_safe.py`
  - 日志显示在 `core/services/scheduler/schedule_optimizer.py` 内访问 `cfg_svc.VALID_DISPATCH_MODES` 时抛出 `AttributeError: '_StubCfgSvc' object has no attribute 'VALID_DISPATCH_MODES'`。
- 失败项 2：`regression_ortools_budget_guard_skip_when_no_time.py`
  - 日志显示同样在 `core/services/scheduler/schedule_optimizer.py` 内访问 `cfg_svc.VALID_DISPATCH_MODES` 时抛出相同 `AttributeError`。
- 失败项 3：`regression_priority_weight_case_insensitive.py`
  - 日志显示断言失败：期望 `total_tardiness_hours == 10.0`，实际为 `9.999722222222223`。

## 结论与取舍（LLM）

### 必须改（P1：阻断回归通过）

- [ ] `schedule_optimizer.py` 对 `cfg_svc.VALID_DISPATCH_MODES` 的硬依赖已破坏两个 OR-Tools 相关 regression 的 stub 契约。
  - 证据：两个失败日志都落在同一行，且报错完全一致。
  - 影响：`optimize_schedule()` 在 `algo_mode="improve"` 分支下，对最小 stub 配置服务不再健壮，导致 OR-Tools 相关保护逻辑回归无法进入真正待验证分支。
  - 建议修复入口：给 `VALID_DISPATCH_MODES` 增加缺省回退，或统一补齐测试 stub 契约；优先选前者可同时恢复运行时鲁棒性。

### 建议改（P2：语义/边界一致性）

- [ ] `regression_priority_weight_case_insensitive.py` 暴露的不是随机波动，而是迟期边界语义差 1 秒。
  - 证据：测试构造的是 `due_date="2026-01-01"`，断言期望 10 小时；实际返回 `9.999722222222223`，恰好比 10 小时少 1 秒。
  - 影响：`compute_metrics()` 对“交期截止点”的解释与该回归用例不一致，可能影响 tardiness / weighted tardiness 指标的边界值展示与验收。
  - 建议修复入口：先确认系统标准是“自然日结束 23:59:59”还是“次日 00:00:00 独占边界”，再决定修实现还是修测试断言。

### 不建议改 / 暂缓

- [x] 其余 smoke、web smoke、FullE2E、复杂 Excel 用例已全部通过，本轮没有证据支持对当前已通过链路做额外扩大修复。

## 成本与风险评估

- 预估总成本：S-M
- 回归风险：中
- 说明：
  - 前两项大概率是同一个入口的一次性修复，成本偏 S。
  - 第三项涉及指标语义，若改实现需补看 `due_exclusive`/`compute_metrics` 相关契约，风险高于前两项。
