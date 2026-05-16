# Full-test-debt shard-count benchmark

## 1. 本次结论

- 结论：暂时不改默认 shard-count，继续保留 `3`。
- 原因：当前已有一份 3 分片 clean proof，真实耗时是 `180.817s`；本次新跑的 4 分片真实墙钟是 `310.71s`，没有证明 4 比 3 更快。
- 本轮是在并行 worker 环境里做的，开跑过程中工作区被其他 worker 改脏，所以 4 分片只能当 dirty 诊断数据，不能当 clean proof。
- 本次留下了可复跑入口：`tools/benchmark_full_test_debt_shards.py`。

## 2. 可复跑命令

只用已有 payload 做轻量分片分布检查：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python tools/benchmark_full_test_debt_shards.py --mode estimate --payload evidence/QualityGate/current_full_test_debt.json --shard-counts 3,4,5,6
```

真实跑指定分片数：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python tools/benchmark_full_test_debt_shards.py --mode run --shard-counts 4 --allow-dirty-worktree-proof
```

如果要拿来改默认值，应该在干净工作区里去掉 `--allow-dirty-worktree-proof`，至少重跑当前默认值和候选值各一次。

## 3. 已有 3 分片 clean proof

- 来源：`evidence/QualityGate/long_gate/results/full_test_debt.success.json`
- completed_at：`2026-05-16T19:42:58`
- command：`python tools/check_full_test_debt.py --sharded --shard-count 3`
- duration_s：`180.816925542`
- nodeid_count：`2592`
- 当前完整门禁 receipt 后续复用了这份 success cache，所以 receipt 自己的 `duration_s=0.267s`，原始真实耗时保存在 `original_duration_s=180.817s`。

## 4. 本次 4 分片实跑

命令：

```bash
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python tools/check_full_test_debt.py --sharded --shard-count 4
```

结果：

| 项目 | 结果 |
|---|---:|
| real | `310.71s` |
| user | `425.97s` |
| sys | `98.08s` |
| collector exitstatus | `0` |
| collected_count | `2594` |
| collection_error_count | `0` |
| failed_nodeid_count | `0` |
| dirty 口径复核 | `passed` |

这次最后命令返回 `2`，原因不是测试失败，而是 `worktree_clean_before=false`。payload 里记录的开跑前脏文件包括：

- `.github/workflows/quality.yml`
- `scripts/run_daily_quality_gate.py`
- `scripts/run_quality_gate.py`
- `tools/quality_gate_shared.py`
- `tools/test_registry.py`
- `tests/test_quality_workflow_cache.py`

后续 `run_check_from_existing_payload(..., require_clean_worktree_proof=False)` 已通过，说明这份 payload 的测试结果本身是绿的。

## 5. 用 4 分片 payload 做的轻量分布检查

这份检查只看 `collected_nodeids`，再按 `tools/full_test_debt_shards.py` 的分片规则重新分配 nodeid。它适合低成本看串行/并行分片规模，不等于真实墙钟时间。

| shard_count | serial_nodeids | parallel_nodeids | max_parallel_nodeids | imbalance |
|---:|---:|---|---:|---:|
| 3 | 856 | `[560, 611, 567]` | `611` | `51` |
| 4 | 856 | `[418, 429, 477, 414]` | `477` | `63` |
| 5 | 856 | `[332, 345, 332, 396, 333]` | `396` | `64` |
| 6 | 856 | `[274, 280, 275, 343, 278, 288]` | `343` | `69` |

从分布看，6 分片会继续降低最大并行分片规模；但本次没有在干净工作区真实跑 6 分片，也没有证明 6 在当前机器上比 3 稳定更快。

## 6. 低风险调整建议

- 本次不改 `scripts/run_quality_gate.py` 或质量门禁里的默认分片数。
- 如果后续要调整，建议只比较 `3` 和 `6`，不要再把 `4/5/6` 全量多轮刷一遍。
- 改默认值前需要满足两个条件：
  - 在干净工作区里真实跑 `3` 和候选值，两个命令都通过 clean proof。
  - 候选值至少快过 `3` 一次，并且没有新增 worker stdout/stderr、collection error、unexpected failure。
