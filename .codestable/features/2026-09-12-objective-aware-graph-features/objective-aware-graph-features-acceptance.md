---
doc_type: feature-acceptance
slug: objective-aware-graph-features
date: 2026-09-12
status: passed-local
tags: [scheduler, graph-ready, objective, due-budget, candidate-coverage]
---

# 验证记录

## 基础父解丢失与修复

首轮实现保留了 9 个 v1 配置和既有 v2 slug，却以 successor/calendar 特征整体替换了旧 v2 排序输入。保留名称没有保住旧 EDD/micro 父解；受限候选池也不能保证其修补邻域仍可访问。

本轮将基础整批排序与增强后继排序明确分开。基础保留原 slug 与 `batch_workload_v1`；增强使用 `v2_successor_*` 和 `operation_successor_v1`。顶层仍为正确的后继工时、piece 数量和日历释放口径，基础启发显式保存在 `graph_ready_baseline_ordering` 子行。两者共用真实 SGS 和正式评分；上限、1 秒内部预算及 5 秒外层预算均未放宽。A 切片负责按同一 feature basis 构建修补信号、在原 top_k 内保留基础/增强代表，以及给动作家族最低探索机会。

限定反事实使用同一真实 shift_pool 输入、当前 decoder 和旧记录的 seed/order/resource inputs：

- 旧基础 EDD、micro 各 48 个工序 priority key 均与旧记录逐项相同；使用增强特征时两者均有 48 个 key 发生变化。
- 基础 EDD 父解恢复为 `(0,1536.5,12,3588.5,289.5,0)`，其真实 `tardy_boundary_move` 解码为 `(0,1423.5,12,3058.5,294.5,0)`。
- 增强 micro 仍实际生成不同父解 `(0,1460.5,11,2028,268.5,0)`，没有删除增强能力。
- 对应证据位于 `/private/tmp/aps-algorithm-implementation-20260912/e-feature-counterfactual-before.json`；它是限定诊断证据，不是正式同预算矩阵。

## 最终定向测试

2026-09-12，在共享未提交工作区运行：

```bash
.venv/bin/python -m pytest -q \
  tests/algorithm/test_optimizer_objective_aware_graph_features.py \
  tests/algorithm/test_optimizer_graph_ready_candidate_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py \
  tests/algorithm/test_graph_ready_v2_zero_quantity_features.py \
  tests/algorithm/test_optimizer_profile_predecode_dedup.py \
  tests/algorithm/test_optimizer_profile_budget.py \
  --junitxml=/private/tmp/aps-algorithm-implementation-20260912/e-final-tests.xml
```

结果：**199 passed in 5.88s**。

合同覆盖：

- 四目标 profile、feature、真实 SGS 和正式 score 贯通；完整默认 29 个/加权及换型 31 个身份与版本，前缀先保基础 micro/EDD，再访问增强目标首选。
- 同公式不同 basis 按 slug 分开核对，不再以 formula_slug 字典覆盖其中一种；benchmark 按完整生产顺序、身份和版本核验覆盖，拒绝数量相同但替换身份的伪造结果。
- 基础与增强工时/窗口明确分开；两者 rank cache 与逐次构造的 priority key 一致。基础子行缺失时明确拒绝，不静默使用增强值。
- 真实旧 EDD 父解到 1423.5 的邻域决策路径、增强 micro 的 1460.5 父解均由生产 evaluator 解码锁定。
- 原后继量纲继续通过：4h→4h 后道负担/毛窗口为 4/4；停机只使净容量变为 2，不把净容量代替毛预算。
- piece 菱形、共享后继只计一次、跨 piece 外协组独立、固定 seed 完工、跨日毛日历、坏图/坏交期/缺字段明确拒绝等合同继续通过。
- 既有零工时、无交期、资源容量、predecode 去重、同预算保留与真实 graph 基准通过。

## 静态检查与交付边界

- 6 个 E 产品模块和本轮新增合同模块使用正式 `tools.quality_gate_scan.scan_complexity_entries` / `scan_oversize_entries`：均无超限；阈值仍为复杂度 15、文件 500 行。
- E 产品与相关测试/benchmark helper 共 10 个 Python 文件：Ruff、Python 3.8 AST 语法与限定 `git diff --check` 通过。这不是 Windows 7 实机验证。
- 文件清单、行数、SHA-256 与结构扫描结果在 `/private/tmp/aps-algorithm-implementation-20260912/e-final-source-manifest.json`，测试 JUnit 如上。
- 未提交或推送，未修改生产数据和依赖。UI 及其他并行切片改动保留。

以上为共享 dirty worktree 的局部验证，不是 clean-worktree proof。真实 1 秒/5 秒的最终质量矩阵、容量矩阵与整仓门禁由主线程对最终冻结源统一执行；限定父解合同不替代该验收。
