---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "bug-03"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 03：未知排产状态仍可能被汇总数量推成“成功”

## 速答

词表设计已经拍板：未知状态，包括旧的 `ok2` 残值，都应该显示“有问题，需检查”。但当前实现里，如果 `result_status` 是未知值，而 summary 里的数量看起来全成功，系统仍可能把它推成“成功”。

## 关键证据

- `web/viewmodels/scheduler_summary_result_state.py:149` — 先把原始 `result_status` 归一化。
- `web/viewmodels/scheduler_summary_result_state.py:150` — 只对已知状态走 `_known_completion_status`。
- `web/viewmodels/scheduler_summary_result_state.py:156` — 未知状态只要 summary 没显式错误，就继续往下走。
- `web/viewmodels/scheduler_summary_result_state.py:158` — 最后根据成功/失败数量推导 completion status。
- `tests/web_pages/test_history_summary_parser.py:140` — 现有 `ok2` 测试只用空 `{}` summary，没有覆盖“未知状态 + 全成功计数”的组合。
- `.codestable/semantics/concepts/schedule-result-status.md:25` — 语义文档明确要求未知值显示“有问题，需检查”。

## 影响

大白话说，系统已经决定“不认识的状态不能装作成功”。但现在还有一条旁路：状态不认识，数量看起来成功，于是又被算回成功。历史脏值或未来写入方写错值时，用户可能看到“成功”，而不是看到需要检查。

## 修复方向

未知 `result_status` 应该优先级高于 summary 数量推断。除非有明确的兼容规则说明某个旧值等价于成功，否则未知值直接返回 `unknown`。回归测试要覆盖 `result_status="ok2"` 或其他未知值，同时 summary 带 `scheduled_ops == total_ops`、`failed_ops == 0` 的场景。

## 建议动作

建议走 `cs-issue`，因为这是用户可见结果误判。
