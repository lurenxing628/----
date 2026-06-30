---
doc_type: issue-fix
issue: 2026-06-30-benchmark-parallel-workers
path: fast-track
fix_date: 2026-06-30
status: completed
severity: P2
tags:
  - scheduler
  - benchmark
  - parallel-workers
---

# Benchmark Parallel Workers Fix Note

## 背景

- 用户反馈中跑和长跑基准测试运行时 CPU 占用偏低，怀疑没有用多核。
- 核查后确认：长跑按 seed 串行执行；中跑外壳串行调度三个子基准，且 FJSP、SMTWT、SGS 大资源池子脚本缺少统一的并行工作进程参数。

## 修复范围

- 新增 `tests/_support/benchmark_parallel.py`，集中定义默认工作进程数 `10`，并提供保持输出顺序的进程池执行工具。
- `benchmark_optimizer_long_run.py` 新增 `--workers`，默认 `10`，按 seed 并行执行，输出和报告记录 workers。
- `benchmark_optimizer_medium_gate.py` 新增 `--workers`，默认 `10`，并把该参数传给三个子基准。
- `benchmark_optimizer_compare_algorithms.py` 和 `optimizer_compare_algorithms.py` 新增 `--workers`，默认 `10`，按 seed 并行执行，保持原输出顺序。
- `benchmark_fjsp.py` 新增 `--workers`，按实例/折叠策略/算法模式组合并行执行。
- `benchmark_smtwt_localsearch.py` 新增 `--workers`，按实例并行执行，失败实例仍回传主进程统一记录。
- `benchmark_sgs_large_resource_pool.py` 新增 `--workers`，按独立基准用例并行执行；当前只有两个用例，因此最多实际使用两个工作进程。
- 更新 `test_optimizer_benchmark_ratchet_gate.py` 和 `test_optimizer_compare_algorithms_contract.py`，锁住长跑、中跑和算法对比默认 `workers=10` 的合同。

## 验证

- `python3 -m ruff check tests/_support/benchmark_parallel.py tests/_support/optimizer_compare_algorithms.py tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py tests/_scripts_e2e/benchmark_optimizer_long_run.py tests/_scripts_e2e/benchmark_optimizer_medium_gate.py tests/_scripts_e2e/benchmark_smtwt_localsearch.py tests/_scripts_e2e/benchmark_fjsp.py tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/algorithm/test_optimizer_compare_algorithms_contract.py`
- `python3 -m py_compile tests/_support/benchmark_parallel.py tests/_support/optimizer_compare_algorithms.py tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py tests/_scripts_e2e/benchmark_optimizer_long_run.py tests/_scripts_e2e/benchmark_optimizer_medium_gate.py tests/_scripts_e2e/benchmark_smtwt_localsearch.py tests/_scripts_e2e/benchmark_fjsp.py tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/algorithm/test_optimizer_compare_algorithms_contract.py`
- `python3 -m pytest tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/algorithm/test_optimizer_compare_algorithms_contract.py -q`
- `python3 tests/_scripts_e2e/benchmark_optimizer_medium_gate.py --run --workers 10`
- `python3 tests/_scripts_e2e/benchmark_optimizer_long_run.py --seeds 10 --workers 10 --no-write`
- `python3 tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py --profiles greedy,graph_ready_v1 --seeds 2 --workers 10 --no-write --allow-dirty-proof`

## 结果

- 中跑真实执行通过，输出 `workers=10`，三个子基准均返回成功。
- 长跑真实执行通过，输出 `workers=10`，`seed_count=10`，状态为 `passed`。
- 算法对比长门禁旁路执行通过，输出 `workers=10`，`seed_count=2`，状态为 `passed`。
- 上述 benchmark 证明来自当前 dirty worktree 的功能检查，只能说明脚本行为自洽；不能当作 clean proof，也不能替代最新 HEAD 上的完整质量门禁。
