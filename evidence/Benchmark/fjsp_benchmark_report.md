# FJSP 基准评测报告（APS）

- 生成时间：2026-03-16 02:16:11
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk01**（10 jobs x 6 machines；BKS=40）
  - 最佳：improve + B_balanced makespan=53.0000h gap=32.50% time=3410ms
  - greedy + A_shortest: makespan=83.0000h gap=107.50% failed_ops=0 time=49ms util_avg=0.307229 load_cv=0.904727
  - greedy + B_balanced: makespan=63.0000h gap=57.50% failed_ops=0 time=42ms util_avg=0.460317 load_cv=0.225240
  - improve + B_balanced: makespan=53.0000h gap=32.50% failed_ops=0 time=3410ms util_avg=0.547170 load_cv=0.225240

- **mk04**（15 jobs x 8 machines；BKS=60）
  - 最佳：improve + B_balanced makespan=81.0000h gap=35.00% time=7844ms
  - greedy + A_shortest: makespan=203.0000h gap=238.33% failed_ops=0 time=54ms util_avg=0.266010 load_cv=1.119056
  - greedy + B_balanced: makespan=87.0000h gap=45.00% failed_ops=0 time=53ms util_avg=0.551724 load_cv=0.297924
  - improve + B_balanced: makespan=81.0000h gap=35.00% failed_ops=0 time=7844ms util_avg=0.592593 load_cv=0.297924

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：improve + B_balanced makespan=89.0000h gap=56.14% time=9087ms
  - greedy + A_shortest: makespan=129.0000h gap=126.32% failed_ops=0 time=53ms util_avg=0.426357 load_cv=0.600734
  - greedy + B_balanced: makespan=99.0000h gap=73.68% failed_ops=0 time=52ms util_avg=0.476768 load_cv=0.071408
  - improve + B_balanced: makespan=89.0000h gap=56.14% failed_ops=0 time=9087ms util_avg=0.530337 load_cv=0.071408

- **mk08**（20 jobs x 10 machines；BKS=523）
  - 最佳：improve + B_balanced makespan=602.0000h gap=15.11% time=20052ms
  - greedy + A_shortest: makespan=749.0000h gap=43.21% failed_ops=0 time=102ms util_avg=0.368491 load_cv=0.636064
  - greedy + B_balanced: makespan=655.0000h gap=25.24% failed_ops=0 time=101ms util_avg=0.443766 load_cv=0.515576
  - improve + B_balanced: makespan=602.0000h gap=15.11% failed_ops=0 time=20052ms util_avg=0.482835 load_cv=0.515576

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：improve + B_balanced makespan=329.0000h gap=70.47% time=20059ms
  - greedy + A_shortest: makespan=497.0000h gap=157.51% failed_ops=0 time=106ms util_avg=0.412922 load_cv=0.424405
  - greedy + B_balanced: makespan=409.0000h gap=111.92% failed_ops=0 time=166ms util_avg=0.489442 load_cv=0.099450
  - improve + B_balanced: makespan=329.0000h gap=70.47% failed_ops=0 time=20059ms util_avg=0.608455 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

