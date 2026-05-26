---
doc_type: audit-finding
audit: quality-gate-cache
finding_id: finding-01
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
created: 2026-05-26
tags: [quality-gate, long-gate, fingerprint]
---

# 公共 tooling hash 导致多个 long gate entry 同时失效

## 结论

long gate 不是所有 entry 共用一个总指纹，但所有 success cache 都会先比较 runner/tooling 版本 hash。`scripts/run_quality_gate.py` 或 `tools/long_gate_*.py` 这类公共工具文件一变，多个 entry 会一起判定为 `tooling version changed` 或 runner changed，旧成功缓存全部不能用。

## 证据

- `tools/long_gate_schema.py:17` 定义 runner 版本只看 `scripts/run_quality_gate.py`。
- `tools/long_gate_schema.py:18` 定义 tooling 版本包含 `tools/long_gate_cache.py`、`tools/long_gate_fingerprint.py`、`tools/long_gate_manifest.py` 等公共文件。
- `tools/long_gate_cache.py:553` 比较 `runner_version_hash` 和 `tooling_version_hash`，不一致就返回 `run`。
- `evidence/QualityGate/long_gate/summary.json` 当前记录显示多个 enabled entry 的 reason 是 `tooling version changed`，其中 `full_test_debt` 实跑约 `204.724s`。

## 风险

- 小的门禁工具改动会触发大面积重跑。
- 直接放宽这个校验会影响最终 clean proof，因为旧缓存可能来自旧 runner 或旧 cache 判定规则。

## 建议

保留严格校验，但把公共 tooling 拆成更细的 entry tooling scope；先做诊断命令，确认某个改动实际会影响哪些 entry。

