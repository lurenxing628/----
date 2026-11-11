---
name: aps-fjsp-benchmark
description: 按明确要求运行 APS 的 Brandimarte FJSP 基准并评价调度结果。仅讨论 FJSP、makespan、数据集含义或算法设计时不运行基准。
---

# APS FJSP 基准测试

## 选择运行范围

先按用户要求选择模式；未指定规模的“跑一下基准”使用 standard，明确要求快速冒烟时用 fast，完整对比才用 full。使用项目 `.venv` Python；以下 `python` 为已激活环境后的简写：

```bash
python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode standard
python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode fast
python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode full
```

脚本不传模式时仍默认 full；调用时显式传入选定模式，不能把脚本默认值当作用户授权。报告：`evidence/Benchmark/fjsp_benchmark_report.md`。

## 必须保留的评价边界

- 不修改排产算法实现；基准运行与评价不自动授权算法修复。
- 基准脚本使用临时 SQLite DB，不写入 `db/aps.db`，不能为解决运行失败切到真实库。
- makespan 主导口径：批次统一 `due_date=2099-12-31`、注入含周末的 24h WorkCalendar，在 `min_overdue` 下主要按 `makespan_hours` 区分，评价函数见 `core/algorithms/evaluation.py` 的 `objective_score`。
- APS 会将 FJSP 的多机可选、工时随机器变化折叠为单机绑定。gap 只能作为参考对照，报告必须披露这一不可直接比较的边界。
- `valid=false` 或 `failed_ops>0` 时先定位日历、解析或资源问题，不据无效结果下性能结论。
- `--time-budget <seconds>` 控制 improve 时间预算，默认 20；`--allow-download` 允许从 GitHub raw 下载实例，失败回退内置镜像。默认离线可跑，不因提到公开数据集自动联网。

## 汇报与完成

说明实例范围、模式、预算、有效性、makespan/利用率/gap、improve 相对 greedy 的收益与耗时、折叠策略 A/B 差异及局限。不把单次结果推广为整体算法最优性，不把基准通过当作质量门禁或 clean proof。

原始报告保留在 `evidence/Benchmark/`。默认在对话中评价；需要保存额外审阅报告时按当前授权写到 `.codestable/audits/` 或流程指定位置。
