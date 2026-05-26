---
doc_type: audit-finding
audit: quality-gate-cache
finding_id: finding-02
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
created: 2026-05-26
tags: [quality-gate, full-test-debt, incremental]
---

# full-test-debt 只有有限增量，没有失败项级别复用

## 结论

`full_test_debt` 已有 special mode：治理台账单独变更可以复用旧测试观察，安全测试文件变更可以只跑受影响 nodeid。但它不是“上次少数失败，下次只重跑失败项”的机制；失败结果不能成为后续 success cache 基础，源码、模板、静态资源、工具和环境变化也会回落全量。

## 证据

- `tools/long_gate_full_test_debt.py:686` 的 `_classify_incremental_plan()` 只接受 ledger-only 或安全测试文件范围。
- `tools/long_gate_full_test_debt.py:726` 对非安全测试文件范围返回 full run。
- `tools/long_gate_full_test_debt.py:1134` 增量 collector 只跑选出的 `selected_nodeids`。
- `tools/long_gate_full_test_debt.py:1224` 合并 payload 时按 changed test files 替换旧报告。
- `tools/check_full_test_debt.py:535` 直接执行 `run_check()` 时每次都先 collect 当前 payload，不读取 node cache。

## 风险

- 少数失败后仍可能付出 full-test-debt 的大头耗时。
- 如果贸然把失败结果缓存成可复用 proof，会有旧失败/旧通过混进最终证明的风险。

## 建议

不要改通用 success cache。若要优化，先在 `full_test_debt` special mode 内做更细的 selected-nodeid 替换，并新增失败项级别的可信收据设计。

