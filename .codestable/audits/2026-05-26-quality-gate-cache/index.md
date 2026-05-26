---
doc_type: audit-index
slug: quality-gate-cache
scope: scripts/run_quality_gate.py, scripts/run_daily_quality_gate.py, tools/long_gate_*.py, tools/git_hook_*.py
summary: 质量门禁和 pre-push 缓存专项审查，判断指纹变化导致重跑是否值得优化
status: current
created: 2026-05-26
tags: [quality-gate, cache, pre-push, performance]
---

# Quality Gate Cache Audit

## 范围

- 完整大门禁：`scripts/run_quality_gate.py`、`tools/long_gate_cache.py`、`tools/long_gate_fingerprint.py`、`tools/long_gate_manifest.py`、`tools/long_gate_full_test_debt.py`
- 日常 pre-push：`.pre-commit-config.yaml`、`.git/hooks/pre-push`、`tools/git_hook_checks.py`、`tools/git_hook_cache.py`、`scripts/run_daily_quality_gate.py`
- 历史证据：`reports/quality_gate_performance_before_after.md`、`reports/full_test_debt_shard_benchmark.md`、`evidence/QualityGate/long_gate/summary.json`

## 总评

当前不是一个总指纹绑死所有大门禁；每个 entry 有自己的 scope。但公共 tooling / runner 版本 hash 和部分 entry 的 scope 比较宽，所以小改动会让多个 enabled entry 一起失效，用户体感接近“指纹一变就全重跑”。

不建议直接放宽 success cache 的精确指纹校验，因为它承载最终 clean proof 的证据链。更合适的改法是分层做：

1. pre-push 先优化，因为它只是本地快反馈，不声明最终证明。
2. 完整大门禁优先增加诊断和缩小公共 scope。
3. full-test-debt 增量只在 special mode 内扩展，不动通用 `evaluate_reuse()` 的严格规则。

## 发现清单

| ID | 性质 | 严重度 | 置信度 | 标题 | 建议动作 |
|---|---|---:|---|---|---|
| finding-01 | performance | P1 | high | 公共 tooling hash 导致多个 long gate entry 同时失效 | cs-refactor |
| finding-02 | performance | P1 | high | full-test-debt 只有有限增量，没有失败项级别复用 | cs-refactor |
| finding-03 | performance | P2 | high | pre-push daily cache key 太粗，小变化会整条重跑 | cs-refactor |
| finding-04 | performance | P2 | medium | architecture_fitness 仍是 planned-only，不能复用 | cs-refactor |

## 下一步建议

1. 先改 pre-push：降低 `head_sha` 对缓存命中的影响，用 tree / diff 范围做 key，并让无 upstream 的新分支也能用 pre-push stdin 算范围。
2. 再给 long gate 加“路径影响诊断”：输入改动路径，输出会失效哪些 entry，先把浪费看清楚。
3. 最后再拆 long gate 公共 tooling scope；不要直接把指纹不一致改成可复用。

