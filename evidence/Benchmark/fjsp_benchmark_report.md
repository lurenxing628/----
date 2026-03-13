# FJSP 基准评测报告（APS）

- 生成时间：2026-03-13 13:15:54
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：improve + B_balanced makespan=84.0000h gap=47.37% time=34330ms
  - greedy + A_shortest: makespan=129.0000h gap=126.32% failed_ops=0 time=90ms util_avg=0.426357 load_cv=0.600734
  - greedy + B_balanced: makespan=99.0000h gap=73.68% failed_ops=0 time=111ms util_avg=0.476768 load_cv=0.071408
  - improve + A_shortest: makespan=111.0000h gap=94.74% failed_ops=0 time=51336ms util_avg=0.495495 load_cv=0.600734
  - improve + B_balanced: makespan=84.0000h gap=47.37% failed_ops=0 time=34330ms util_avg=0.561905 load_cv=0.071408

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：improve + B_balanced makespan=319.0000h gap=65.28% time=60110ms
  - greedy + A_shortest: makespan=497.0000h gap=157.51% failed_ops=0 time=212ms util_avg=0.412922 load_cv=0.424405
  - greedy + B_balanced: makespan=409.0000h gap=111.92% failed_ops=0 time=186ms util_avg=0.489442 load_cv=0.099450
  - improve + A_shortest: makespan=415.0000h gap=115.03% failed_ops=0 time=60110ms util_avg=0.494511 load_cv=0.424405
  - improve + B_balanced: makespan=319.0000h gap=65.28% failed_ops=0 time=60110ms util_avg=0.627529 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

