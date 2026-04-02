# FJSP 基准评测报告（APS）

- 生成时间：2026-04-02 17:07:46
- 数据集：Brandimarte (1993) FJSP，来源 `Lei-Kun/FJSP-benchmarks`
- 口径：统一 `due_date=2099-12-31` + 注入 24h WorkCalendar，使优化器主要按 makespan 比较（见 `core/algorithms/evaluation.py` 的 objective_score）。
- 重要局限：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，因此 gap 只能做参考对照。

## 汇总（按实例）

- **mk01**（10 jobs x 6 machines；BKS=40）
  - 最佳：improve + B_balanced makespan=53.0000h gap=32.50% time=3272ms
  - greedy + A_shortest: makespan=83.0000h gap=107.50% failed_ops=0 time=45ms util_avg=0.307229 load_cv=0.904727
  - greedy + B_balanced: makespan=63.0000h gap=57.50% failed_ops=0 time=41ms util_avg=0.460317 load_cv=0.225240
  - improve + A_shortest: makespan=76.0000h gap=90.00% failed_ops=0 time=3493ms util_avg=0.335526 load_cv=0.904727
  - improve + B_balanced: makespan=53.0000h gap=32.50% failed_ops=0 time=3272ms util_avg=0.547170 load_cv=0.225240

- **mk04**（15 jobs x 8 machines；BKS=60）
  - 最佳：improve + B_balanced makespan=81.0000h gap=35.00% time=7151ms
  - greedy + A_shortest: makespan=203.0000h gap=238.33% failed_ops=0 time=50ms util_avg=0.266010 load_cv=1.119056
  - greedy + B_balanced: makespan=87.0000h gap=45.00% failed_ops=0 time=49ms util_avg=0.551724 load_cv=0.297924
  - improve + A_shortest: makespan=194.0000h gap=223.33% failed_ops=0 time=7802ms util_avg=0.278351 load_cv=1.119056
  - improve + B_balanced: makespan=81.0000h gap=35.00% failed_ops=0 time=7151ms util_avg=0.592593 load_cv=0.297924

- **mk06**（10 jobs x 10 machines；BKS=57）
  - 最佳：improve + B_balanced makespan=89.0000h gap=56.14% time=8586ms
  - greedy + A_shortest: makespan=129.0000h gap=126.32% failed_ops=0 time=52ms util_avg=0.426357 load_cv=0.600734
  - greedy + B_balanced: makespan=99.0000h gap=73.68% failed_ops=0 time=49ms util_avg=0.476768 load_cv=0.071408
  - improve + A_shortest: makespan=110.0000h gap=92.98% failed_ops=0 time=11042ms util_avg=0.500000 load_cv=0.600734
  - improve + B_balanced: makespan=89.0000h gap=56.14% failed_ops=0 time=8586ms util_avg=0.530337 load_cv=0.071408

- **mk08**（20 jobs x 10 machines；BKS=523）
  - 最佳：improve + B_balanced makespan=602.0000h gap=15.11% time=20056ms
  - greedy + A_shortest: makespan=749.0000h gap=43.21% failed_ops=0 time=96ms util_avg=0.368491 load_cv=0.636064
  - greedy + B_balanced: makespan=655.0000h gap=25.24% failed_ops=0 time=95ms util_avg=0.443766 load_cv=0.515576
  - improve + A_shortest: makespan=649.0000h gap=24.09% failed_ops=0 time=20077ms util_avg=0.425270 load_cv=0.636064
  - improve + B_balanced: makespan=602.0000h gap=15.11% failed_ops=0 time=20056ms util_avg=0.482835 load_cv=0.515576

- **mk10**（20 jobs x 15 machines；UB=193）
  - 最佳：improve + B_balanced makespan=329.0000h gap=70.47% time=20063ms
  - greedy + A_shortest: makespan=497.0000h gap=157.51% failed_ops=0 time=90ms util_avg=0.412922 load_cv=0.424405
  - greedy + B_balanced: makespan=409.0000h gap=111.92% failed_ops=0 time=84ms util_avg=0.489442 load_cv=0.099450
  - improve + A_shortest: makespan=431.0000h gap=123.32% failed_ops=0 time=20117ms util_avg=0.476154 load_cv=0.424405
  - improve + B_balanced: makespan=329.0000h gap=70.47% failed_ops=0 time=20063ms util_avg=0.608455 load_cv=0.099450

## 结论（自动摘要）

- 本报告仅提供“可重复运行的量化对照”；最终评价以你对业务目标（交期/换型/利用率）权衡为准。

