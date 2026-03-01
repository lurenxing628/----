# FJSP 基准评测报告（APS）

- 生成时间：2026-03-02 00:58:49
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk01**（10 jobs x 6 machines；BKS=40）
  - 最佳：improve + B_balanced makespan=44.0000h gap=10.00% time=1018ms
  - greedy + A_shortest: makespan=83.0000h gap=107.50% failed_ops=0 time=50ms util_avg=0.307229 load_cv=0.904727
  - greedy + B_balanced: makespan=63.0000h gap=57.50% failed_ops=0 time=44ms util_avg=0.460317 load_cv=0.225240
  - improve + B_balanced: makespan=44.0000h gap=10.00% failed_ops=0 time=1018ms util_avg=0.659091 load_cv=0.225240

- **mk04**（15 jobs x 8 machines；BKS=60）
  - 最佳：improve + B_balanced makespan=80.0000h gap=33.33% time=1760ms
  - greedy + A_shortest: makespan=203.0000h gap=238.33% failed_ops=0 time=55ms util_avg=0.266010 load_cv=1.119056
  - greedy + B_balanced: makespan=87.0000h gap=45.00% failed_ops=0 time=53ms util_avg=0.551724 load_cv=0.297924
  - improve + B_balanced: makespan=80.0000h gap=33.33% failed_ops=0 time=1760ms util_avg=0.600000 load_cv=0.297924

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：improve + B_balanced makespan=95.0000h gap=66.67% time=2290ms
  - greedy + A_shortest: makespan=129.0000h gap=126.32% failed_ops=0 time=96ms util_avg=0.426357 load_cv=0.600734
  - greedy + B_balanced: makespan=99.0000h gap=73.68% failed_ops=0 time=72ms util_avg=0.476768 load_cv=0.071408
  - improve + B_balanced: makespan=95.0000h gap=66.67% failed_ops=0 time=2290ms util_avg=0.496842 load_cv=0.071408

- **mk08**（20 jobs x 10 machines；BKS=523）
  - 最佳：improve + B_balanced makespan=562.0000h gap=7.46% time=5059ms
  - greedy + A_shortest: makespan=749.0000h gap=43.21% failed_ops=0 time=118ms util_avg=0.368491 load_cv=0.636064
  - greedy + B_balanced: makespan=655.0000h gap=25.24% failed_ops=0 time=113ms util_avg=0.443766 load_cv=0.515576
  - improve + B_balanced: makespan=562.0000h gap=7.46% failed_ops=0 time=5059ms util_avg=0.517200 load_cv=0.515576

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：improve + B_balanced makespan=325.0000h gap=68.39% time=4985ms
  - greedy + A_shortest: makespan=497.0000h gap=157.51% failed_ops=0 time=102ms util_avg=0.412922 load_cv=0.424405
  - greedy + B_balanced: makespan=409.0000h gap=111.92% failed_ops=0 time=99ms util_avg=0.489442 load_cv=0.099450
  - improve + B_balanced: makespan=325.0000h gap=68.39% failed_ops=0 time=4985ms util_avg=0.615944 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

