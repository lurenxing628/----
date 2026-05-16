---
doc_type: refactor
status: applied
created_at: 2026-05-11
updated_at: 2026-05-11
slug: quality-gate-resume-locatable
---

# 质量门禁续跑与失败定位证据链优化

## 范围

本轮只治理质量门禁、full test debt collector/checker、以及 sync debt ledger 的测试债务 baseline 导入入口。

## 非目标

- 不改排产算法。
- 不改导入保存业务逻辑。
- 不改页面业务逻辑。

## 约束

`--allow-dirty-worktree` 下的续跑只用于本地快速反馈；即使续跑通过，也只能生成 `passed_but_unbound`，不能作为 clean proof。最终证明仍必须在干净工作区完整执行 `scripts/run_quality_gate.py --require-clean-worktree`。
