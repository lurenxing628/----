---
doc_type: audit-finding
audit: quality-gate-cache
finding_id: finding-04
nature: performance
severity: P2
confidence: medium
suggested_action: cs-refactor
status: open
created: 2026-05-26
tags: [quality-gate, architecture-fitness, cache]
---

# architecture_fitness 仍是 planned-only，不能复用

## 结论

`architecture_fitness` 是 long gate candidate，但不在 cache enabled 列表里。即使其他 entry 命中 success cache，这个 entry 仍不会走 long gate success cache。

## 证据

- `tools/long_gate_manifest.py:50` 把 `architecture_fitness` 放在 long entry types。
- `tools/long_gate_manifest.py:63` 的 cache enabled entry types 不包含 `architecture_fitness`。
- 当前 `evidence/QualityGate/long_gate/summary.json` 中 `architecture_fitness` 的 `cache_status` 是 `planned`，decision 是 `planned_only`。

## 风险

- 它不是主要耗时来源，但会造成“怎么还有门禁没复用”的体感。
- 如果直接启用缓存而没有精确定义 scope，可能复用到不该复用的架构检查结果。

## 建议

补明确 scope 和测试后再启用，或者在 summary 里更醒目标注它当前就是 planned-only。

