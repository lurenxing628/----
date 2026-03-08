---
description: 运行 Brandimarte FJSP 基准并汇总 makespan、utilization 与 gap，生成 evidence/Benchmark/fjsp_benchmark_report.md
---
当用户提到“基准测试 / benchmark / FJSP / Brandimarte / makespan / 排产数据集 / 调度数据集”或要求“用公开数据集跑跑看”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-fjsp-benchmark/SKILL.md`

1. 先确认运行模式。
   - 默认全量矩阵：`python .windsurf/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py`
   - 标准模式：`python .windsurf/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode standard`
   - 快速 smoke：`python .windsurf/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode fast`

2. 牢记口径约束。
   - 只跑基准、生成证据与评价，不修改排产算法实现。
   - 使用临时 SQLite DB，不污染 `db/aps.db`。
   - makespan 是主导指标。
   - APS 对 FJSP 的柔性机会折叠为单机绑定，因此 gap 只能参考，报告里必须写清局限性。

3. 跑完后读取报告。
   - `evidence/Benchmark/fjsp_benchmark_report.md`

4. 输出结论时至少包含。
   - 哪个组合 makespan 最好。
   - improve 相比 greedy 的收益与耗时成本。
   - 如果 `valid=false` 或 `failed_ops>0`，先定位原因，不给性能结论。
   - 明确说明对比边界和不可比因素。

5. 常用参数。
   - `--mode fast|standard|full`
   - `--time-budget <seconds>`
   - `--allow-download`：允许从 GitHub raw 下载实例；默认通常不需要联网。
