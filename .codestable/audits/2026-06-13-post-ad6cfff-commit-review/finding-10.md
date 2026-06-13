---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "arch-drift-10"
nature: arch-drift
severity: P2
confidence: high
suggested_action: cs-refactor
status: resolved
---

# Finding 10：部分验收和文档没有把路线图闭环、页面说明、测试说明同步干净

## 速答

这批提交里有不少 acceptance 文档写了“roadmap 回写 done”，但机器可读 items 里仍有 `feature: null`；另外一些页面文案和旧 smoke 测试还停在旧口径。它们不是运行时主链路 bug，但会让后续维护者和自动检索误判当前状态。

## 关键证据

- `.codestable/roadmap/aps-frontend-fusion/aps-frontend-fusion-items.yaml:61` — `fusion-label-single-source` 已是 `status: done`。
- `.codestable/roadmap/aps-frontend-fusion/aps-frontend-fusion-items.yaml:65` — 同一条仍是 `feature: null`。
- `templates/scheduler/week_plan.html:80` — 页面仍说导出字段是 7 项：日期 / 批次号 / 图号 / 工序 / 设备 / 人员 / 时段。
- `tests/_scripts_e2e/smoke_phase8.py:316` — 旧 smoke 仍按 7 列读取周计划表头。
- `static/js/gantt_chain_walk.js:131` — 沿链巡检没有目标时，提示固定说“关键链后续工序在当前日期范围/筛选之外”，上一道方向也会显示“后续”。

## 影响

大白话说，功能可能已经能跑，但台账没有完全跟上。后续有人按 roadmap 查“这个条目由哪个 feature 完成”，会查不到 feature 指针；用户或维护者按页面文案/旧 smoke 理解周计划导出，会以为仍是旧 7 列；甘特链路空结果文案会让用户分不清是在找上一道还是下一道。

## 修复方向

这类问题适合一次小文档/台账收口：

- done 的 roadmap item 补回对应 feature 目录。
- 周计划页面文案、导出测试和实际表头保持一致。
- 甘特链路巡检文案按方向显示“上一道/下一道”。
- acceptance 文档里如果声称 clean-worktree proof 或 roadmap 回写，应能对应到实际 git/status/YAML 证据。

## 建议动作

建议走 `cs-refactor` 或小范围文档修复，因为主要是追踪资料、测试说明和用户说明同步。
