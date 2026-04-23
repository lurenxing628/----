---
name: aps-fjsp-benchmark
description: 使用 tests/benchmark_fjsp.py 运行 Brandimarte FJSP 基准（mk01/mk04/mk06/mk08/mk10），生成 evidence/Benchmark/fjsp_benchmark_report.md，并汇总 makespan、利用率与 gap。适用于用户提到基准测试、FJSP、Brandimarte、makespan、排产数据集、调度数据集等场景。
---

# APS FJSP 基准测试（Brandimarte）

## Quick start

- 默认（全量矩阵，推荐）：`python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py`
- 标准（最小矩阵，更快）：`python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode standard`
- 快速 smoke（仅 mk01）：`python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode fast`

输出报告：

- `evidence/Benchmark/fjsp_benchmark_report.md`

## 适用场景（触发词）

- 用户提到：**基准测试 / benchmark / FJSP / Brandimarte / makespan / 排产数据集 / 调度数据集**
- 用户要求：**用公开数据集跑跑看**、**评价当前算法**、**跑一下 FJSP 基准**

## 约束与口径（必须遵守）

- **不修改排产算法实现**：只跑基准、生成证据与评价。
- **不污染真实库**：基准脚本使用临时 SQLite DB（不会写入 `db/aps.db`）。
- **makespan 主导口径**：
  - 批次统一 `due_date=2099-12-31`
  - 注入 24h WorkCalendar（含周末）
  - 让优化器在 `min_overdue` 下主要按 `makespan_hours` 区分（见 `core/algorithms/evaluation.py` 的 `objective_score`）
- **重要局限**：FJSP 的“多机可选且工时随机器变化”在 APS 模型里会折叠为单机绑定，gap 只能做参考对照（报告必须写清楚）。

## 工作流（给 Agent 的执行指引）

1. 运行 runner（默认 full 矩阵）：
   - `python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py`
2. 读取并摘要报告：
   - `evidence/Benchmark/fjsp_benchmark_report.md`
3. 若出现 `valid=false` 或 `failed_ops>0`：
   - 不做性能结论；先定位原因（日历覆盖/数据解析/资源缺失等）
4. 输出给用户的结论至少包含：
   - 哪个组合 makespan 最好（improve vs greedy、折叠策略 A/B）
   - improve 的收益与耗时成本
   - 局限性边界（折叠柔性导致不可比）

## 参数说明（常用）

- `--mode fast|standard|full`：默认 `full`
- `--time-budget <seconds>`：improve 模式时间预算（默认 20）
- `--allow-download`：允许从 GitHub raw 下载实例（失败会回退内置镜像，默认不需要联网）

