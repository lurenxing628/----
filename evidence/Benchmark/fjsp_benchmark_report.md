# FJSP 基准评测报告（APS）

- 生成时间：2026-06-29 01:24:24
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk01**（10 jobs x 6 machines；BKS=40）
  - 最佳：greedy + B_balanced makespan=51.0000h gap=27.50% time=54ms
  - greedy + A_shortest: makespan=73.0000h gap=82.50% failed_ops=0 time=124ms util_avg=0.349315 load_cv=0.904727
  - greedy + B_balanced: makespan=51.0000h gap=27.50% failed_ops=0 time=54ms util_avg=0.568627 load_cv=0.225240
  - improve + B_balanced: makespan=51.0000h gap=27.50% failed_ops=0 time=98ms util_avg=0.568627 load_cv=0.225240

- **mk04**（15 jobs x 8 machines；BKS=60）
  - 最佳：improve + B_balanced makespan=79.0000h gap=31.67% time=190ms
  - greedy + A_shortest: makespan=188.0000h gap=213.33% failed_ops=0 time=155ms util_avg=0.287234 load_cv=1.119056
  - greedy + B_balanced: makespan=83.0000h gap=38.33% failed_ops=0 time=121ms util_avg=0.578313 load_cv=0.297924
  - improve + B_balanced: makespan=79.0000h gap=31.67% failed_ops=0 time=190ms util_avg=0.607595 load_cv=0.297924

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：greedy + B_balanced makespan=90.0000h gap=57.89% time=141ms
  - greedy + A_shortest: makespan=101.0000h gap=77.19% failed_ops=0 time=182ms util_avg=0.544554 load_cv=0.600734
  - greedy + B_balanced: makespan=90.0000h gap=57.89% failed_ops=0 time=141ms util_avg=0.524444 load_cv=0.071408
  - improve + B_balanced: makespan=90.0000h gap=57.89% failed_ops=0 time=233ms util_avg=0.524444 load_cv=0.071408

- **mk08**（20 jobs x 10 machines；BKS=523）
  - 最佳：greedy + B_balanced makespan=532.0000h gap=1.72% time=500ms
  - greedy + A_shortest: makespan=587.0000h gap=12.24% failed_ops=0 time=518ms util_avg=0.470187 load_cv=0.636064
  - greedy + B_balanced: makespan=532.0000h gap=1.72% failed_ops=0 time=500ms util_avg=0.546366 load_cv=0.515576
  - improve + B_balanced: makespan=532.0000h gap=1.72% failed_ops=0 time=689ms util_avg=0.546366 load_cv=0.515576

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：greedy + B_balanced makespan=277.0000h gap=43.52% time=462ms
  - greedy + A_shortest: makespan=401.0000h gap=107.77% failed_ops=0 time=545ms util_avg=0.511776 load_cv=0.424405
  - greedy + B_balanced: makespan=277.0000h gap=43.52% failed_ops=0 time=462ms util_avg=0.722678 load_cv=0.099450
  - improve + B_balanced: makespan=277.0000h gap=43.52% failed_ops=0 time=639ms util_avg=0.722678 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

