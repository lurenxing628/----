---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-06
nature: bug
severity: P3
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 06：图档配置 batch_order 时实际以 sgs 解码，CandidatePlan.dispatch_mode 与持久化列仍记 batch_order

## 速答

`schedule_candidate_runner.py` 取 `candidate_cfg.dispatch_mode` 而非 `outcome.dispatch_mode`（`schedule_optimizer.py:169` 已是 "sgs"），持久化列跟着记配置值，sgs 这个事实无处可查。

## 关键证据

- `core/services/scheduler/run/schedule_candidate_runner.py:460`；`schedule_candidate_persistence_models.py:91`。

## 影响

审计留痕失真；读列方目前只有模型与写入，无消费者。

## 修复方向

`CandidatePlan.dispatch_mode` 取 `outcome.dispatch_mode`，持久化如实。

## 处理结果

2026-09-18 同日落地：运行器按职责拆出 `core/services/scheduler/run/schedule_candidate_plan.py`，`adopted_dispatch_mode(outcome, cfg)` 取 outcome 的模式、缺字段才回落配置；复用方案沿用兄弟的模式；持久化列随方案字段。合同测试 `tests/candidate/test_scheduler_candidate_corrections_contract.py`。
