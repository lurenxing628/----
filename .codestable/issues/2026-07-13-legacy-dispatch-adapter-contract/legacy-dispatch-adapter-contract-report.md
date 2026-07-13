---
doc_type: issue-report
issue: 2026-07-13-legacy-dispatch-adapter-contract
status: confirmed
severity: P1
summary: direct legacy batch-order 在 strict 模式下接受非法工时并退化成无原因的普通失败
tags: [algorithm, dispatch, strict-mode, compatibility]
---

# Legacy dispatch adapter 合同回归 Issue Report

## 1. 问题现象

把 legacy scheduler-like 对象直接传给 `dispatch_batch_order` 且启用 `strict_mode=True` 时，非法工时没有以字段明确的 `ValidationError` 阻断；legacy `_schedule_internal` 仍被调用，入口最终只返回失败计数，错误列表为空。

当 legacy 对象缺少私有 scheduling / auto-assign callback 时，新适配器也会在工序循环内部抛 `TypeError`，随后被折算成普通 dispatch failure，而不是在入口明确暴露 context 合同不完整。

## 2. 复现步骤

1. 构造带 `_schedule_internal` callback 的 legacy scheduler-like 对象。
2. 构造 `setup_hours="not-a-number"` 的内部工序和合法批次。
3. 调用 `dispatch_batch_order(..., strict_mode=True)`。
4. 观察到返回 `(0, 1)`、callback 调用 1 次且 `errors=[]`。

复现频率：稳定，100%。

## 3. 期望 vs 实际

**期望行为**：strict 模式应在 legacy callback 执行前校验工时，非法值抛出 `ValidationError(field="setup_hours")`；legacy context 缺少当前执行路径实际用到的 callback 时，应明确抛出合同错误且不得被折算成普通 dispatch failure。

**实际行为**：`strict_mode` 被适配器直接删除，callback 仍执行；缺 callback 的 `TypeError` 发生在逐工序 try/except 内，可被折算为普通失败。

## 4. 环境信息

- 涉及模块 / 功能：贪心算法 batch-order / SGS dispatch context 兼容边界
- 相关文件 / 函数：`core/algorithm_runtime/dispatch_context.py::_LegacyDispatchContext`、`ensure_dispatch_context`
- 运行环境：当前开发分支 `feat/default-light-improve-sgs`，`HEAD=6433599d`
- 其他上下文：由未推送提交审计发现；A3 实现提交为 `f422b88c`

## 5. 严重程度

**P1** - 主 `GreedyScheduler` 当前使用完整 context，不直接触发；但 A3 声称保留的 direct/legacy 入口破坏了 strict fail-loud，非法输入会丢失具体错误原因，应在 push 前修复。

## 备注

来源审计：`.codestable/audits/2026-07-13-unpushed-dependency-governance-review/finding-01.md`。
