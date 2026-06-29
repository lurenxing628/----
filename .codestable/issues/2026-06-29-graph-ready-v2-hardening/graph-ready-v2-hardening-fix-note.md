---
doc_type: fix-note
status: done
slug: graph-ready-v2-hardening
date: 2026-06-29
owners:
  - codex
related:
  - .codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md
  - .codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json
  - core/services/scheduler/run/optimizer_graph_ready.py
  - core/services/scheduler/run/optimizer_graph_ready_candidates.py
  - core/services/scheduler/run/optimizer_graph_ready_profiles.py
  - core/services/scheduler/run/optimizer_graph_ready_v2_features.py
---

# GraphReady v2 加固修复记录

## 背景

本次任务要把 GraphReady v2 修扎实，重点不是让报告看起来更漂亮，而是把四个容易误导人的地方补住：

- 特征语义：v2 排序用到的交期压力、剩余批次工作量、瓶颈释放价值等字段，必须来自真实排程对象和真实目标口径，缺字段或坏字段要直接失败，不能悄悄给默认值。
- 候选有效性：候选必须通过正式 SGS 解码结果、目标分数和输出指纹证明自己真的不一样，不能把同一个排程输出重复算成新改进。
- 对比诚实性：多算法对比里，失败行、空分数、分数长度不一致、缺参考算法都不能算赢；组合最优也只能从通过且分数有效的行里挑。
- 证据链：脏工作区下只能说当前现场自洽，不能说干净提交证明；没有真最优求解器或可比参考时，不能给 `gap_to_oracle_pct` 填假数字。

## 根因

- v2 特征抽取原先有静默默认值风险，容易让“缺数据”伪装成“低风险特征值”。
- v2 候选评分曾经混用小时、比例、图得分等不同量尺，容易让某个单位大的字段压过其他字段。
- 对比脚本早期只看是否有一组分数，没有严格区分“失败行”“空分数”“短分数”“缺参考”，容易把不可比较的行算成改进。
- benchmark 证据里曾把 oracle 信息写得太满，实际 GraphReady v2 当前没有 APS 真最优 oracle，不能证明全局最优。
- 脏工作区 proof 原本容易被人误读成 clean proof，需要让脚本默认拒绝脏现场证明。

## 修复范围

- `core/services/scheduler/run/optimizer_graph_ready_v2_features.py`
  - 新增 v2 目标感知特征抽取。
  - 对缺工序、缺批次、坏交期、坏工时直接抛 `ValidationError`。
  - 对归一化后重复的 `node_metrics_by_op_id` 直接抛 `ValidationError`，避免 `1` 和 `"1"` 这类等价键静默互相覆盖。
  - `remaining_work_hours` 改成同批次、可排工序、且在图指标覆盖范围内的剩余工时合计。
  - 移除容易误读的剩余产能字段。

- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`
  - v2 先做排序百分位归一化，再生成优先级键，避免不同单位直接硬加。
  - 把“越容易救的批次优先”和“剩余工作越短越容易救”写进候选排序。
  - 微扰动同时绑定 seed 和工序号，保证不同 seed 能产生可追踪的候选变化。

- `core/services/scheduler/run/optimizer_graph_ready_profiles.py`
  - 在 profile 摘要里明确写入 v1/v2 公式版本和 v2 归一化版本，避免把混合评估说成纯 v2。

- `tests/_support/optimizer_graph_ready_v2_benchmark.py`
  - v2 行只有在 best origin 来自 v2、比分严格优于 v1、候选输出确实不同、无失败工序时才通过。
  - oracle 字段改成 `not_run` 和 `gap_to_oracle_pct=null`，不再假装有 APS 全局最优 gap。
  - repair 标成 benchmark 支撑能力，不包装成核心生产修复。
  - `accepted_distinct_candidates` 改成按已接受输出指纹集合长度统计，不再混用接受次数。

- `tests/_support/optimizer_compare_algorithms.py`
  - 缺参考、失败行、空分数、非法分数、分数长度不一致统一标成不可比较。
  - `portfolio_all` 只从通过且分数有效且形状一致的来源里挑；没有合格来源时不伪造 best。
  - `distinct_candidates` 和 `accepted_distinct_candidates` 改成按正式输出指纹去重。

- `tests/_support/optimizer_smtwt_compare_*.py`
  - SMTWT 单机形状检查复用同一套诚实比较口径。
  - 修复 repair 替换 best 后，origin、目标分数、best 指纹、accepted 指纹可能不一致的问题。
  - 报告里明确 SMTWT 不是 APS 图约束、多机资源约束、全局最优证明。

- `tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py`
  - 默认要求 clean proof。
  - 脏工作区下不带 `--allow-dirty-proof` 会失败。
  - 带 `--allow-dirty-proof` 只能得到 `unbound_dirty_worktree`，不能得到 clean proof。

- `tests/_scripts_e2e/benchmark_optimizer_smtwt_compare_algorithms.py`
  - 同样补上 dirty proof 检查，避免单机 benchmark 被包装成干净证明。

- `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`
  - 更新当前多算法对比基线。
  - 基线明确记录 `dirty_worktree=true` 和 `proof_binding_status=unbound_dirty_worktree`。

## 验证结果

- 目标单测：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_reference_diagnostics_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 结果：`69 passed`

- GraphReady v2 重复键边界：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/algorithm/test_optimizer_graph_ready_candidate_contract.py -k "duplicate_normalized_metric_ids or graph_ready_v2"`
  - 结果：`26 passed, 9 deselected`。

- 静态检查：
  - 命令：`.venv/bin/python -m ruff check ...`
  - 结果：`All checks passed!`

- 空白和语法检查：
  - 命令：`git diff --check`
  - 结果：通过，无输出。
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q ...`
  - 结果：通过，无输出。

- 参考诊断：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_reference_diagnostics.py --no-write`
  - 结果：`status=passed`，`comparable_reference_count=1`，`not_comparable_reference_count=4`。

- 多算法对比，严格 proof：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all --seeds 10 --check-baseline --no-write`
  - 结果：按预期失败，`proof_check.status=failed`，原因是 `dirty_actual_worktree`；baseline 也拒绝脏证明。

- 多算法对比，允许脏 proof：
  - 命令：同上并加 `--allow-dirty-proof`
  - 结果：脚本通过，但 `proof_binding_status=unbound_dirty_worktree`，`dirty_worktree=true`。
  - GraphReady v1：10/10 比当前 baseline 改进，平均主指标变化 `-1.0`。
  - GraphReady v2 no repair：10/10 比当前 baseline 改进，平均主指标变化 `-2.0`。
  - GraphReady v2 with repair：10/10 比当前 baseline 改进，平均主指标变化 `-2.0`。
  - `portfolio_all` 与 v2 达到同一档平均主指标变化 `-2.0`。

- SMTWT 单机形状检查，严格 proof：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_smtwt_compare_algorithms.py --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all --sizes 40 --limit-per-size 2 --seeds 1 --workers 1 --no-write --summary-only`
  - 结果：按预期失败，`proof_check.status=failed`，原因是 `dirty_actual_worktree`。

- SMTWT 单机形状检查，允许脏 proof：
  - 命令：同上并加 `--allow-dirty-proof`
  - 结果：脚本通过，但 `proof_binding_status=unbound_dirty_worktree`，`dirty_worktree=true`。
  - v2 no repair 对 v1：2 胜 0 平 0 负。
  - v2 no repair 对 grasp_ig：2 胜 0 平 0 负。
  - v2 no repair 对 greedy/local_search：各 2 胜 0 平 0 负。
  - v2 no repair 对 portfolio_all：0 胜 2 平 0 负。

- APS 快速门禁：
  - 命令：`.venv/bin/python scripts/run_quality_gate.py --fast-precheck`
  - 结果：通过；该命令自己声明这不是完整质量门禁。

- APS 完整 clean proof 入口：
  - 命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`
  - 结果：按预期失败，原因是工作区不干净；错误点包括未跟踪源码文件 `core/services/scheduler/run/optimizer_graph_ready_v2_features.py`。

## 对“是否更接近全局最优”的诚实结论

- 可以说：在当前 GraphReady real SGS 小样本比较里，v2 的主指标比 v1 更好，并且与 `portfolio_all` 持平。
- 可以说：在 SMTWT 单机形状检查里，v2 no repair 对 v1、greedy、local_search、grasp_ig 都赢，对 `portfolio_all` 持平。
- 不能说：已经证明 APS 全局最优。
- 不能说：已经证明 v2 离全局最优的 gap 是多少。
- 原因很直接：当前 GraphReady v2 real SGS case 没有运行可比 oracle，报告里已经写成 `oracle_status=not_run`，`gap_to_oracle_pct=null`；参考诊断也只有一个 tiny case 可比，另外四个参考不可比或数据不可用。

## 子代理复审

- 本轮使用了多轮定向复审和盲审复审。
- 最后一轮盲审结论是 `zero-blocker`。
- 盲审补充的两个非阻塞建议已经处理：
  - SMTWT 行补上 `accepted_distinct_candidates`。
  - GraphReady benchmark 的 `accepted_distinct_candidates` 改成直接按 accepted 指纹集合长度统计。
- 额外顺手补齐了 GraphReady v2 专用 benchmark 的同名字段，让普通 GraphReady、GraphReady v2、SMTWT 三条证据链口径一致。

## 剩余边界

- 当前工作区是脏的，不能给 clean proof。
- 没有对完整仓库跑通 clean quality gate，因为 clean gate 会先拒绝脏工作区。
- v2 当前仍是 benchmark / candidate profile 证据链加固，不等于生产默认调度路径已经切到 v2。
- benchmark repair 明确是 benchmark support，不是核心生产 repair。
