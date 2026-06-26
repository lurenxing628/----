# FJSP 基准评测报告（APS）

- 生成时间：2026-06-25 23:20:26
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk01**（10 jobs x 6 machines；BKS=40）
  - 最佳：improve + B_balanced makespan=44.0000h gap=10.00% time=22912ms
  - greedy + A_shortest: makespan=73.0000h gap=82.50% failed_ops=0 time=152ms util_avg=0.349315 load_cv=0.904727
  - greedy + B_balanced: makespan=51.0000h gap=27.50% failed_ops=0 time=83ms util_avg=0.568627 load_cv=0.225240
  - improve + B_balanced: makespan=44.0000h gap=10.00% failed_ops=0 time=22912ms util_avg=0.659091 load_cv=0.225240

- **mk04**（15 jobs x 8 machines；BKS=60）
  - 最佳：improve + B_balanced makespan=81.0000h gap=35.00% time=26677ms
  - greedy + A_shortest: makespan=188.0000h gap=213.33% failed_ops=0 time=244ms util_avg=0.287234 load_cv=1.119056
  - greedy + B_balanced: makespan=83.0000h gap=38.33% failed_ops=0 time=193ms util_avg=0.578313 load_cv=0.297924
  - improve + B_balanced: makespan=81.0000h gap=35.00% failed_ops=0 time=26677ms util_avg=0.592593 load_cv=0.297924

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：greedy + B_balanced makespan=90.0000h gap=57.89% time=217ms
  - greedy + A_shortest: makespan=101.0000h gap=77.19% failed_ops=0 time=276ms util_avg=0.544554 load_cv=0.600734
  - greedy + B_balanced: makespan=90.0000h gap=57.89% failed_ops=0 time=217ms util_avg=0.524444 load_cv=0.071408
  - improve + B_balanced: makespan=90.0000h gap=57.89% failed_ops=0 time=26037ms util_avg=0.524444 load_cv=0.071408

- **mk08**（20 jobs x 10 machines；BKS=523）
  - 最佳：greedy + B_balanced makespan=532.0000h gap=1.72% time=803ms
  - greedy + A_shortest: makespan=587.0000h gap=12.24% failed_ops=0 time=829ms util_avg=0.470187 load_cv=0.636064
  - greedy + B_balanced: makespan=532.0000h gap=1.72% failed_ops=0 time=803ms util_avg=0.546366 load_cv=0.515576
  - improve + B_balanced: makespan=532.0000h gap=1.72% failed_ops=0 time=23599ms util_avg=0.546366 load_cv=0.515576

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：greedy + B_balanced makespan=277.0000h gap=43.52% time=724ms
  - greedy + A_shortest: makespan=401.0000h gap=107.77% failed_ops=0 time=846ms util_avg=0.511776 load_cv=0.424405
  - greedy + B_balanced: makespan=277.0000h gap=43.52% failed_ops=0 time=724ms util_avg=0.722678 load_cv=0.099450
  - improve + B_balanced: makespan=287.0000h gap=48.70% failed_ops=0 time=23329ms util_avg=0.697498 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

