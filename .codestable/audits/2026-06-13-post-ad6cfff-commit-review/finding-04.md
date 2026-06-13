---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "maintainability-04"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
status: resolved
---

# Finding 04：版本下拉框仍有第二套状态文案，复合标签会被压扁

## 速答

`fusion-label-single-source` 的目标是把状态文案收成唯一字源，避免一个地方叫 A、另一个地方叫 B。当前版本下拉框还保留第二套 `_VERSION_OPTION_STATUS_LABELS`，并且会把“模拟排产 / 部分成功”这类复合标签压成“部分成功”。

## 关键证据

- `web/viewmodels/scheduler_history_summary.py:29` — 仍有 `_VERSION_OPTION_STATUS_LABELS` 独立字典。
- `web/viewmodels/scheduler_history_summary.py:251` — 下拉框从 `display_state.result_state.outcome_status` 再查一遍字典。
- `web/viewmodels/scheduler_history_summary.py:253` — `result_text` 优先使用第二套字典，只有查不到时才回退 `row["result_status_label"]`。
- `.codestable/semantics/concepts/schedule-result-status.md:22` — 语义文档要求模板和行级数据消费 `result_status_label` / `version_option_label`，不要再各处查词表。

## 影响

这会带来两个问题：

- 维护问题：状态文案又变成两份，以后改一处容易漏另一处。
- 展示问题：模拟排产这种复合标签本来能告诉用户“这是模拟排产 + 结果状态”，下拉框可能只显示最终 outcome，少了方案身份。

## 修复方向

版本下拉框应该直接消费统一的展示标签，不要再维护第二套状态字典。若确实需要下拉框专用拼接，也应该从同一个 `result_status_display_label` 或统一 viewmodel 字段派生。

## 建议动作

建议走 `cs-refactor`，因为目标是删除重复字源、收拢展示口径，行为上应保持语义一致但更少重复。
